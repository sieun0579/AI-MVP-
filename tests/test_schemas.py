import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data" / "source_manifest.json"
DOCUMENT_SCHEMA_PATH = ROOT / "schemas" / "document.schema.json"
MEMORY_SCHEMA_PATH = ROOT / "schemas" / "memory.schema.json"
EVAL_SCHEMA_PATH = ROOT / "schemas" / "eval_case.schema.json"


def load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def test_json_files_parse():
    for path in (
        MANIFEST_PATH,
        DOCUMENT_SCHEMA_PATH,
        MEMORY_SCHEMA_PATH,
        EVAL_SCHEMA_PATH,
    ):
        assert load_json(path)


def test_manifest_entries_match_document_schema():
    manifest = load_json(MANIFEST_PATH)
    schema = load_json(DOCUMENT_SCHEMA_PATH)
    validator = jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    )
    errors = []
    for index, source in enumerate(manifest["sources"]):
        errors.extend(
            f"sources[{index}]: {error.message}"
            for error in validator.iter_errors(source)
        )
    assert errors == []


def test_manifest_has_expected_verified_page_count():
    manifest = load_json(MANIFEST_PATH)
    assert len(manifest["sources"]) == 54


def test_source_ids_and_notion_urls_are_unique():
    sources = load_json(MANIFEST_PATH)["sources"]
    source_ids = [source["source_id"] for source in sources]
    notion_urls = [source["notion_url"] for source in sources]
    assert len(source_ids) == len(set(source_ids))
    assert len(notion_urls) == len(set(notion_urls))


def test_parent_references_resolve():
    sources = load_json(MANIFEST_PATH)["sources"]
    source_ids = {source["source_id"] for source in sources}
    unresolved = {
        source["source_id"]: source["parent_source_id"]
        for source in sources
        if source["parent_source_id"]
        and source["parent_source_id"] not in source_ids
    }
    assert unresolved == {}


def test_evaluation_material_is_not_runtime():
    sources = load_json(MANIFEST_PATH)["sources"]
    evaluation_markers = ("채점표", "회고 질문 정답", "저장 12·제외 5")
    leaked = [
        source["source_id"]
        for source in sources
        if source["data_scope"] == "runtime"
        and any(marker in source["title"] for marker in evaluation_markers)
    ]
    assert leaked == []


def test_mixed_pages_require_split():
    sources = load_json(MANIFEST_PATH)["sources"]
    invalid = [
        source["source_id"]
        for source in sources
        if source["source_type"] == "mixed_page"
        and (
            source["data_scope"] == "runtime"
            or source["conversion_status"] != "requires_split"
        )
    ]
    assert invalid == []


def test_schema_documents_are_valid_draft_2020_12():
    for path in (
        DOCUMENT_SCHEMA_PATH,
        MEMORY_SCHEMA_PATH,
        EVAL_SCHEMA_PATH,
    ):
        jsonschema.Draft202012Validator.check_schema(load_json(path))
