"""Convert read-only Notion fetch snapshots into scope-separated JSON corpora."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


class ConversionError(RuntimeError):
    """Raised when source data is missing or cannot be converted safely."""


H2_PATTERN = re.compile(r"^##\s+(.+?)\s*$")
CONTENT_PATTERN = re.compile(r"<content>\n?(.*?)\n?</content>", re.DOTALL)

RUNTIME_EVALUATION_HEADINGS = ("후임자 확인",)
RUNTIME_DEVELOPMENT_HEADINGS = ("챗봇 활용 예시", "챗봇 시연 문장")

SPECIAL_LINE_SCOPES: dict[str, dict[str, str]] = {
    "container-integrated-context": {
        "후임자 문제·정답·근거": "evaluation",
        "챗봇 시연 문장": "development",
    },
    "manual-index": {
        "후임자 확인 문제": "evaluation",
    },
}

# Mixed pages are deny-by-default: only explicitly mapped headings reach runtime.
MIXED_SECTION_SCOPES: dict[str, dict[str, str]] = {
    "container-program-context": {
        "가상 기업 설정": "runtime",
        "표준 업무 매뉴얼": "runtime",
        "이 Context의 구성 원칙": "runtime",
        "프로젝트 분류": "runtime",
        "경험 연결 지도": "runtime",
        "챗봇 실험에 쓰는 방법": "development",
        "문서 상태 기준": "runtime",
    },
    "container-integrated-context": {
        "표준 업무 매뉴얼": "runtime",
        "통합 방향": "runtime",
        "18개 원천 → 12개 최종 프로젝트": "runtime",
        "삭제하지 않고 통합한 이유": "runtime",
        "프로젝트 공통 상세 양식": "runtime",
        "경험 연결 지도": "runtime",
        "기억 상태와 기계적 적용 방지": "runtime",
        "MVP 구현 전 보완 자료": "development",
        "원천": "development",
    },
    "PREP-01": {
        "문서 상태 범례": "runtime",
        "현재 규정 8종": "runtime",
        "충돌하는 구버전 4종": "runtime",
        "프로젝트 예외 규정 3종": "runtime",
        "승인 전 초안 2종": "development",
        "충돌 정답표": "evaluation",
        "MVP 기대 동작": "evaluation",
    },
    "PREP-04": {
        "22명 조직도": "runtime",
        "권한표": "runtime",
        "역할별 시나리오 3종": "runtime",
        "민감자료 6종": "runtime",
        "차단 정답": "evaluation",
        "감사": "development",
    },
    "PREP-07": {
        "Before Project": "runtime",
        "During Project": "runtime",
        "문제 발생과 현장 대응": "runtime",
        "After Project": "runtime",
        "AI 회고 질문": "runtime",
        "구조화된 조직기억 카드": "runtime",
        "Next Project": "runtime",
        "후임자 확인 문제와 정답": "evaluation",
        "챗봇 시연 문장": "development",
    },
}


def _load_json(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise ConversionError(f"missing source data: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConversionError(f"invalid JSON source data: {path}") from exc


def _extract_content(fetch_text: str, source_id: str) -> str:
    match = CONTENT_PATTERN.search(fetch_text)
    if not match:
        raise ConversionError(f"Notion content block is missing: {source_id}")
    content = match.group(1).replace("<empty-block/>", "").strip()
    if not content:
        raise ConversionError(f"Notion content is empty: {source_id}")
    return content


def _split_h2_sections(content: str) -> list[tuple[str | None, str]]:
    blocks: list[tuple[str | None, list[str]]] = [(None, [])]
    for line in content.splitlines():
        match = H2_PATTERN.match(line)
        if match:
            blocks.append((match.group(1).strip(), [line]))
        else:
            blocks[-1][1].append(line)
    return [(heading, "\n".join(lines).strip()) for heading, lines in blocks if "\n".join(lines).strip()]


def _route_ready_section(default_scope: str, heading: str | None) -> str:
    if default_scope != "runtime" or heading is None:
        return default_scope
    if any(marker in heading for marker in RUNTIME_EVALUATION_HEADINGS):
        return "evaluation"
    if any(marker in heading for marker in RUNTIME_DEVELOPMENT_HEADINGS):
        return "development"
    return "runtime"


def _route_mixed_section(source_id: str, heading: str | None) -> str:
    if heading is None:
        return "development"
    return MIXED_SECTION_SCOPES.get(source_id, {}).get(heading, "development")


def _route_special_lines(
    source_id: str,
    scope: str,
    heading: str | None,
    block: str,
) -> list[tuple[str, tuple[str | None, str]]]:
    """Move sensitive index lines without deleting their source content."""
    rules = SPECIAL_LINE_SCOPES.get(source_id, {}) if scope == "runtime" else {}
    if not rules:
        return [(scope, (heading, block))]

    remaining: list[str] = []
    moved: list[tuple[str, tuple[str | None, str]]] = []
    for line in block.splitlines():
        target_scope = next(
            (target for marker, target in rules.items() if marker in line),
            None,
        )
        if target_scope:
            moved.append((target_scope, (heading, line.strip())))
        else:
            remaining.append(line)

    remaining_text = "\n".join(remaining).strip()
    output = [(scope, (heading, remaining_text))] if remaining_text else []
    output.extend(moved)
    return output


def _make_document(
    source: dict[str, Any],
    payload: dict[str, Any],
    scope: str,
    blocks: list[tuple[str | None, str]],
    conversion_mode: str,
) -> dict[str, Any]:
    text = "\n\n".join(block for _, block in blocks).strip()
    if not text:
        raise ConversionError(f"routed content is empty: {source['source_id']}::{scope}")
    headings = [heading for heading, _ in blocks if heading]
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    verification = payload.get("verification") or {}
    return {
        "document_id": f"{source['source_id']}::{scope}",
        "source_id": source["source_id"],
        "title": source["title"],
        "source_type": source["source_type"],
        "data_scope": scope,
        "status": source["status"],
        "effective_date": source["effective_date"],
        "allowed_roles": source["allowed_roles"],
        "related_projects": source["related_projects"],
        "source": {
            "notion_url": source["notion_url"],
            "page_last_edited_at": payload.get("page_last_edited_at"),
            "path": payload.get("path", ""),
            "verification_state": verification.get("state", "unknown"),
        },
        "content": {
            "format": "notion_markdown",
            "text": text,
            "char_count": len(text),
            "sha256": digest,
        },
        "conversion": {
            "mode": conversion_mode,
            "included_sections": headings,
        },
    }


def build_corpora(root: Path) -> dict[str, dict[str, Any]]:
    """Build deterministic corpora from locally captured Notion fetch snapshots."""
    manifest = _load_json(root / "data" / "source_manifest.json")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    converted_source_ids: set[str] = set()

    for source in manifest["sources"]:
        if source["conversion_status"] == "excluded_from_runtime":
            continue
        source_id = source["source_id"]
        raw = _load_json(root / "data" / "raw" / "notion" / f"{source_id}.json")
        if raw.get("source_id") != source_id:
            raise ConversionError(f"source identity mismatch: {source_id}")
        payload = raw.get("payload") or {}
        fetch_text = payload.get("text")
        if not isinstance(fetch_text, str):
            raise ConversionError(f"Notion fetch text is missing: {source_id}")
        content = _extract_content(fetch_text, source_id)
        routed: dict[str, list[tuple[str | None, str]]] = defaultdict(list)
        is_mixed = source["conversion_status"] == "requires_split"
        for heading, block in _split_h2_sections(content):
            if is_mixed:
                scope = _route_mixed_section(source_id, heading)
            else:
                scope = _route_ready_section(source["data_scope"], heading)
            for routed_scope, routed_block in _route_special_lines(
                source_id,
                scope,
                heading,
                block,
            ):
                routed[routed_scope].append(routed_block)

        for scope, blocks in routed.items():
            grouped[scope].append(
                _make_document(
                    source,
                    payload,
                    scope,
                    blocks,
                    "section_split" if is_mixed or len(routed) > 1 else "full_page",
                )
            )
        converted_source_ids.add(source_id)

    expected = {
        source["source_id"]
        for source in manifest["sources"]
        if source["conversion_status"] != "excluded_from_runtime"
    }
    if converted_source_ids != expected:
        missing = sorted(expected - converted_source_ids)
        raise ConversionError(f"unconverted sources: {', '.join(missing)}")

    corpora: dict[str, dict[str, Any]] = {}
    for scope in ("runtime", "development", "evaluation"):
        documents = sorted(grouped[scope], key=lambda item: item["document_id"])
        corpora[scope] = {
            "corpus_version": "2.0.0",
            "scope": scope,
            "source_snapshot_date": manifest["source_snapshot_date"],
            "document_count": len(documents),
            "documents": documents,
        }
    return corpora


def write_corpora(root: Path) -> dict[str, Path]:
    corpora = build_corpora(root)
    output_dir = root / "data" / "converted"
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for scope, corpus in corpora.items():
        path = output_dir / f"{scope}_documents.json"
        path.write_text(
            json.dumps(corpus, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        paths[scope] = path
    return paths
