"""Deterministic, source-grounded search for the MomentLab runtime corpus."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any


NO_DATA_MESSAGE = "확인 가능한 데이터가 없습니다."
TOKEN_PATTERN = re.compile(r"[가-힣]{2,}|[a-z0-9]+", re.IGNORECASE)
HEADING_PATTERN = re.compile(r"^(#{2,6})\s+(.+?)\s*$")
PROJECT_ID_PATTERN = re.compile(r"\b(?:ML|U|P)-\d{2}\b", re.IGNORECASE)

STOPWORDS = {
    "관련",
    "대한",
    "무엇",
    "뭐야",
    "알려줘",
    "어떻게",
    "경우",
    "하는",
    "있는",
    "그리고",
    "하지만",
    "합니다",
    "에서",
    "으로",
    "에게",
}


class ScopeViolation(ValueError):
    """Raised when a non-runtime corpus is supplied to the search engine."""


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _word_tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


def _features(text: str) -> list[str]:
    features: list[str] = []
    for token in _word_tokens(text):
        if token in STOPWORDS:
            continue
        features.append(f"w:{token}")
        if re.fullmatch(r"[가-힣]+", token) and len(token) >= 3:
            features.extend(f"b:{token[index:index + 2]}" for index in range(len(token) - 1))
    return features


def _sections(text: str) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = [("문서 개요", [])]
    for line in text.splitlines():
        match = HEADING_PATTERN.match(line)
        if match:
            sections.append((match.group(2).strip(), [line]))
        else:
            sections[-1][1].append(line)
    return [(title, lines) for title, lines in sections if any(line.strip() for line in lines)]


def _split_lines(lines: list[str], max_chars: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_chars = 0
    for line in lines:
        added = len(line) + (1 if current else 0)
        if current and current_chars + added > max_chars:
            chunks.append("\n".join(current).strip())
            current = []
            current_chars = 0
        current.append(line)
        current_chars += len(line) + (1 if len(current) > 1 else 0)
    if current:
        chunks.append("\n".join(current).strip())
    return [chunk for chunk in chunks if chunk]


def _chunk_document(document: dict[str, Any], max_chars: int) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    sequence = 0
    for section_title, lines in _sections(document["content"]["text"]):
        for text in _split_lines(lines, max_chars=max_chars):
            sequence += 1
            term_frequencies = Counter(_features(text))
            chunks.append(
                {
                    "chunk_id": f"{document['document_id']}::{sequence:03d}",
                    "document_id": document["document_id"],
                    "source_id": document["source_id"],
                    "title": document["title"],
                    "source_type": document["source_type"],
                    "status": document["status"],
                    "effective_date": document["effective_date"],
                    "allowed_roles": document["allowed_roles"],
                    "related_projects": document["related_projects"],
                    "section_title": section_title,
                    "text": text,
                    "notion_url": document["source"]["notion_url"],
                    "page_last_edited_at": document["source"]["page_last_edited_at"],
                    "term_frequencies": dict(sorted(term_frequencies.items())),
                    "term_count": sum(term_frequencies.values()),
                }
            )
    return chunks


def build_search_index(root: Path, max_chars: int = 2200) -> dict[str, Any]:
    corpus_path = root / "data" / "converted" / "runtime_documents.json"
    corpus = _read_json(corpus_path)
    if corpus.get("scope") != "runtime":
        raise ScopeViolation("search indexing accepts runtime corpus only")

    chunks = [
        chunk
        for document in corpus["documents"]
        for chunk in _chunk_document(document, max_chars=max_chars)
    ]
    document_frequencies: Counter[str] = Counter()
    for chunk in chunks:
        document_frequencies.update(chunk["term_frequencies"].keys())

    return {
        "index_version": "1.0.0",
        "scope": "runtime",
        "source_corpus": "data/converted/runtime_documents.json",
        "source_snapshot_date": corpus["source_snapshot_date"],
        "chunk_count": len(chunks),
        "average_term_count": (
            sum(chunk["term_count"] for chunk in chunks) / len(chunks) if chunks else 0
        ),
        "document_frequencies": dict(sorted(document_frequencies.items())),
        "chunks": chunks,
    }


def write_search_index(root: Path) -> Path:
    index = build_search_index(root)
    output = root / "data" / "search" / "runtime_index.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


class ContextSearchEngine:
    """Search an already-built runtime-only context index."""

    def __init__(self, index: dict[str, Any], *, minimum_score: float = 2.0):
        if index.get("scope") != "runtime":
            raise ScopeViolation("search engine accepts runtime index only")
        self.index = index
        self.minimum_score = minimum_score

    @classmethod
    def from_project(cls, root: Path, *, minimum_score: float = 2.0) -> "ContextSearchEngine":
        path = root / "data" / "search" / "runtime_index.json"
        return cls(_read_json(path), minimum_score=minimum_score)

    def _idf(self, term: str) -> float:
        total = self.index["chunk_count"]
        frequency = self.index["document_frequencies"].get(term, 0)
        return math.log(1 + (total - frequency + 0.5) / (frequency + 0.5))

    def _score(self, query_features: list[str], chunk: dict[str, Any]) -> tuple[float, float]:
        frequencies = chunk["term_frequencies"]
        average_length = max(self.index["average_term_count"], 1)
        length = max(chunk["term_count"], 1)
        k1 = 1.5
        b = 0.75
        score = 0.0
        matched_weight = 0.0
        total_weight = 0.0
        for term in query_features:
            weight = 1.0 if term.startswith("w:") else 0.25
            total_weight += weight
            frequency = frequencies.get(term, 0)
            if not frequency:
                continue
            matched_weight += weight
            numerator = frequency * (k1 + 1)
            denominator = frequency + k1 * (1 - b + b * length / average_length)
            score += weight * self._idf(term) * numerator / denominator
        coverage = matched_weight / total_weight if total_weight else 0.0
        return score, coverage

    def search(self, query: str, *, top_k: int = 5) -> dict[str, Any]:
        query = query.strip()
        if not query or top_k < 1:
            return self._no_data(query)
        query_features = _features(query)
        if not query_features:
            return self._no_data(query)

        requested_ids = {item.upper() for item in PROJECT_ID_PATTERN.findall(query)}
        ranked: list[tuple[float, float, dict[str, Any]]] = []
        for chunk in self.index["chunks"]:
            score, coverage = self._score(query_features, chunk)
            if requested_ids and chunk["source_id"].upper() in requested_ids:
                score += 16.0
                coverage = max(coverage, 0.7)
            elif requested_ids and requested_ids.intersection(
                item.upper() for item in chunk["related_projects"]
            ):
                score += 6.0
                coverage = max(coverage, 0.5)
            if score >= self.minimum_score and coverage >= 0.18:
                ranked.append((score, coverage, chunk))

        ranked.sort(key=lambda item: (-item[0], -item[1], item[2]["chunk_id"]))
        results = [
            {
                "rank": rank,
                "score": round(score, 4),
                "query_coverage": round(coverage, 4),
                "chunk_id": chunk["chunk_id"],
                "source_id": chunk["source_id"],
                "title": chunk["title"],
                "section_title": chunk["section_title"],
                "text": chunk["text"],
                "status": chunk["status"],
                "effective_date": chunk["effective_date"],
                "notion_url": chunk["notion_url"],
                "page_last_edited_at": chunk["page_last_edited_at"],
            }
            for rank, (score, coverage, chunk) in enumerate(ranked[:top_k], start=1)
        ]
        if not results:
            return self._no_data(query)
        return {
            "query": query,
            "found": True,
            "message": "관련 Context를 찾았습니다.",
            "result_count": len(results),
            "results": results,
        }

    @staticmethod
    def _no_data(query: str) -> dict[str, Any]:
        return {
            "query": query,
            "found": False,
            "message": NO_DATA_MESSAGE,
            "result_count": 0,
            "results": [],
        }
