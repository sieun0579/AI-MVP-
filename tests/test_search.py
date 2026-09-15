import json
from pathlib import Path

import pytest

from momentlab_context.search import (
    NO_DATA_MESSAGE,
    ContextSearchEngine,
    ScopeViolation,
    build_search_index,
)

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "data" / "search" / "runtime_index.json"
RUNTIME_PATH = ROOT / "data" / "converted" / "runtime_documents.json"
EVALUATION_PATH = ROOT / "data" / "converted" / "evaluation_documents.json"


def load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="module")
def engine():
    return ContextSearchEngine.from_project(ROOT)


def test_index_is_runtime_only_and_has_real_chunks():
    index = load_json(INDEX_PATH)
    runtime = load_json(RUNTIME_PATH)
    runtime_ids = {document["source_id"] for document in runtime["documents"]}
    assert index["scope"] == "runtime"
    assert index["chunk_count"] == len(index["chunks"])
    assert index["chunk_count"] > 0
    assert {chunk["source_id"] for chunk in index["chunks"]} <= runtime_ids


def test_evaluation_sources_are_absent_from_index():
    index_ids = {chunk["source_id"] for chunk in load_json(INDEX_PATH)["chunks"]}
    evaluation_ids = {
        document["source_id"] for document in load_json(EVALUATION_PATH)["documents"]
    }
    evaluation_only_ids = evaluation_ids - {
        document["source_id"] for document in load_json(RUNTIME_PATH)["documents"]
    }
    assert index_ids.isdisjoint(evaluation_only_ids)


def test_every_chunk_is_exact_source_text():
    runtime_text = {
        document["document_id"]: document["content"]["text"]
        for document in load_json(RUNTIME_PATH)["documents"]
    }
    for chunk in load_json(INDEX_PATH)["chunks"]:
        assert chunk["text"] in runtime_text[chunk["document_id"]]


def test_known_weather_question_finds_u03(engine):
    response = engine.search("야외 행사 순간풍속 중단 기준", top_k=3)
    assert response["found"] is True
    assert response["result_count"] > 0
    assert response["results"][0]["source_id"] == "U-03"


def test_company_question_finds_company_context(engine):
    response = engine.search("모먼트랩 부서 조직", top_k=2)
    assert response["found"] is True
    assert response["results"][0]["source_id"] == "container-program-context"


def test_explicit_project_id_prioritizes_that_source(engine):
    response = engine.search("ML-01 대기열 개선", top_k=3)
    assert response["found"] is True
    assert response["results"][0]["source_id"] == "ML-01"


def test_unknown_question_returns_exact_no_data_message(engine):
    response = engine.search("화성 탐사선 핵융합 연료")
    assert response == {
        "query": "화성 탐사선 핵융합 연료",
        "found": False,
        "message": NO_DATA_MESSAGE,
        "result_count": 0,
        "results": [],
    }


def test_empty_question_returns_no_data(engine):
    response = engine.search("   ")
    assert response["found"] is False
    assert response["message"] == NO_DATA_MESSAGE


def test_results_are_evidence_not_generated_answers(engine):
    response = engine.search("개인정보 보관 기간", top_k=4)
    assert "answer" not in response
    assert response["found"] is True
    for result in response["results"]:
        assert result["text"]
        assert result["notion_url"].startswith("https://app.notion.com/p/")
        assert "answer" not in result


def test_same_query_is_deterministic(engine):
    first = engine.search("원격 송출 이중화 기준", top_k=5)
    second = engine.search("원격 송출 이중화 기준", top_k=5)
    assert first == second


def test_non_runtime_index_is_rejected():
    index = load_json(INDEX_PATH)
    index["scope"] = "evaluation"
    with pytest.raises(ScopeViolation, match="runtime index only"):
        ContextSearchEngine(index)


def test_index_build_is_deterministic():
    assert build_search_index(ROOT) == load_json(INDEX_PATH)
