import os
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"

os.environ["MOMENTLAB_DISABLE_LLM"] = "1"


def create_app_test():
    return AppTest.from_file(str(APP_PATH), default_timeout=10).run()


def submit_question(app, question):
    return app.chat_input[0].set_value(question).run()


def test_app_loads_without_exception():
    app = create_app_test()
    assert not app.exception
    assert app.title[0].value == "🧠 MomentLab 조직 기억"
    assert "로컬 AI" in app.info[0].value


def test_known_question_displays_source_results():
    app = create_app_test()
    submit_question(app, "모먼트랩 부서 조직")
    assert not app.exception
    assert any(item.value == "관련 Context를 찾았습니다." for item in app.success)
    assert any("답변" in item.value for item in app.markdown)
    assert any("경영지원팀 / 프로젝트기획팀 / 마케팅팀 / 재무·운영팀" in item.value for item in app.markdown)
    assert any("가상 기업 설정" in item.label for item in app.expander)
    assert len(app.expander) == 1
    assert any("Notion 원문 열기" in item.value for item in app.markdown)


def test_unknown_question_displays_no_data_message():
    app = create_app_test()
    submit_question(app, "화성 탐사선 핵융합 연료")
    assert not app.exception
    assert any(item.value == "확인 가능한 데이터가 없습니다." for item in app.markdown)
    assert any("Context를 찾지 못했습니다." in item.value for item in app.caption)
    assert not app.success
    assert not app.expander


def test_budget_ranking_question_compares_project_budgets():
    app = create_app_test()
    submit_question(app, "예산이 가장 비쌌던 행사 알려줘")
    assert not app.exception
    assert any("ML-06 바다마을 푸드 페스티벌" in item.value for item in app.markdown)
    assert any("실제 총예산은 9,588만 원" in item.value for item in app.markdown)
    assert any("비교 범위: 총예산이 기록된 프로젝트" in item.value for item in app.caption)


def test_empty_submission_requests_a_question():
    app = create_app_test()
    submit_question(app, "   ")
    assert any(item.value == "질문을 입력해 주세요." for item in app.warning)


def test_uses_a_bottom_pinned_chat_input():
    app = create_app_test()
    assert len(app.chat_input) == 1
    assert not app.text_input
    assert not any(button.label == "Context 검색" for button in app.button)


def test_newest_question_is_displayed_first():
    app = create_app_test()
    submit_question(app, "모먼트랩 부서 조직")
    submit_question(app, "예산이 가장 비쌌던 행사 알려줘")
    questions = [item.children[0].value for item in app.chat_message if item.name == "user"]
    assert questions == ["예산이 가장 비쌌던 행사 알려줘", "모먼트랩 부서 조직"]
