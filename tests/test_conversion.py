import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from momentlab_context.converter import ConversionError, _extract_content, build_corpora

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "source_manifest.json"
RAW_DIR = ROOT / "data" / "raw" / "notion"
CONVERTED_DIR = ROOT / "data" / "converted"
SCHEMA = ROOT / "schemas" / "converted_document.schema.json"
SCOPES = ("runtime", "development", "evaluation")


def load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_outputs():
    return {
        scope: load_json(CONVERTED_DIR / f"{scope}_documents.json")
        for scope in SCOPES
    }


def test_all_expected_notion_pages_were_captured():
    manifest = load_json(MANIFEST)
    expected = {
        source["source_id"]
        for source in manifest["sources"]
        if source["conversion_status"] != "excluded_from_runtime"
    }
    captured = {path.stem for path in RAW_DIR.glob("*.json")}
    assert captured == expected
    assert len(captured) == 48


def test_generated_corpus_counts_match_contents_and_scopes():
    outputs = load_outputs()
    for scope, corpus in outputs.items():
        assert corpus["document_count"] == len(corpus["documents"])
        assert corpus["document_count"] > 0
        assert all(document["data_scope"] == scope for document in corpus["documents"])


def test_converted_documents_match_schema():
    schema = load_json(SCHEMA)
    validator = jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    )
    errors = []
    for corpus in load_outputs().values():
        for document in corpus["documents"]:
            errors.extend(error.message for error in validator.iter_errors(document))
    assert errors == []


def test_all_nonexcluded_sources_survive_in_at_least_one_scope():
    manifest = load_json(MANIFEST)
    expected = {
        source["source_id"]
        for source in manifest["sources"]
        if source["conversion_status"] != "excluded_from_runtime"
    }
    converted = {
        document["source_id"]
        for corpus in load_outputs().values()
        for document in corpus["documents"]
    }
    assert converted == expected


def test_evaluation_and_demo_sections_do_not_leak_into_runtime():
    runtime_text = "\n".join(
        document["content"]["text"]
        for document in load_outputs()["runtime"]["documents"]
    )
    forbidden_headings = (
        "후임자 확인 문제",
        "## 후임자 확인",
        "챗봇 활용 예시",
        "챗봇 시연 문장",
        "충돌 정답표",
        "차단 정답",
        "MVP 기대 동작",
    )
    assert all(heading not in runtime_text for heading in forbidden_headings)


def test_evaluation_pages_are_never_runtime_documents():
    manifest = load_json(MANIFEST)
    evaluation_ids = {
        source["source_id"]
        for source in manifest["sources"]
        if source["data_scope"] == "evaluation"
    }
    runtime_ids = {
        document["source_id"]
        for document in load_outputs()["runtime"]["documents"]
    }
    assert evaluation_ids.isdisjoint(runtime_ids)


def test_sensitive_index_lines_are_preserved_outside_runtime():
    outputs = load_outputs()
    runtime_text = "\n".join(
        document["content"]["text"] for document in outputs["runtime"]["documents"]
    )
    evaluation_text = "\n".join(
        document["content"]["text"] for document in outputs["evaluation"]["documents"]
    )
    development_text = "\n".join(
        document["content"]["text"] for document in outputs["development"]["documents"]
    )
    assert "후임자 확인 문제" not in runtime_text
    assert "후임자 확인 문제" in evaluation_text
    assert "후임자 문제·정답·근거" in evaluation_text
    assert "챗봇 시연 문장과 A/B/C 실험 포인트" in development_text


def test_content_lengths_and_hashes_are_exact():
    for corpus in load_outputs().values():
        for document in corpus["documents"]:
            text = document["content"]["text"]
            assert document["content"]["char_count"] == len(text)
            assert document["content"]["sha256"] == hashlib.sha256(
                text.encode("utf-8")
            ).hexdigest()


def test_sources_keep_their_original_notion_urls():
    source_urls = {
        source["source_id"]: source["notion_url"]
        for source in load_json(MANIFEST)["sources"]
    }
    for corpus in load_outputs().values():
        for document in corpus["documents"]:
            assert document["source"]["notion_url"] == source_urls[document["source_id"]]


def test_build_is_deterministic_from_captured_sources():
    assert build_corpora(ROOT) == load_outputs()


def test_missing_or_empty_notion_content_is_rejected_not_fabricated():
    with pytest.raises(ConversionError, match="content block is missing"):
        _extract_content("<page><properties/></page>", "missing-test")
    with pytest.raises(ConversionError, match="content is empty"):
        _extract_content("<page><content>\n<empty-block/>\n</content></page>", "empty-test")
