"""MomentLab organizational-memory chatbot prototype UI."""

from pathlib import Path
import json
import os
import re
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_MODEL = "qwen2.5:3b"

from momentlab_context.search import ContextSearchEngine


st.set_page_config(
    page_title="MomentLab 조직 기억",
    page_icon="🧠",
    layout="centered",
)


@st.cache_resource
def load_engine() -> ContextSearchEngine:
    return ContextSearchEngine.from_project(ROOT)


def render_result_card(result: dict) -> None:
    label = f"{result['rank']}. {result['title']} · {result['section_title']}"
    with st.expander(label, expanded=result["rank"] == 1):
        status = result["status"] or "미지정"
        effective_date = result["effective_date"] or "미지정"
        st.caption(
            f"문서 ID: {result['source_id']} · 상태: {status} · "
            f"적용일: {effective_date} · 검색 점수: {result['score']} · "
            f"질문어 일치율: {result.get('query_coverage', 0):.0%}"
        )
        st.text(result["text"])
        st.markdown(f"[Notion 원문 열기]({result['notion_url']})")


def extract_context_answer(question: str, response: dict) -> str:
    """Return the most question-relevant source statement without inventing facts."""
    source_text = response["results"][0]["text"]
    question_terms = set(re.findall(r"[가-힣]{2,}|[a-z0-9]+", question.lower()))
    candidates: list[tuple[int, int, str]] = []

    for position, line in enumerate(source_text.splitlines()):
        line = re.sub(r"^#{1,6}\s+", "", line).strip()
        line = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line)
        line = re.sub(r"\*\*(.*?)\*\*", r"\1", line).strip()
        if not line or line.startswith("<") or line.endswith(">"):
            continue
        matched_terms = sum(term in line.lower() for term in question_terms)
        label = line.split(":", maxsplit=1)[0].lower()
        if label in question_terms:
            matched_terms += 2
        candidates.append((matched_terms, -position, line))

    if not candidates:
        return source_text.strip()
    return max(candidates)[2]


def find_budget_ranking_answer(engine: ContextSearchEngine, question: str) -> dict | None:
    """Answer budget superlatives by comparing project totals, not keyword matches."""
    asks_for_ranking = any(word in question for word in ("가장", "제일", "최고", "많은", "비싼", "큰"))
    if "예산" not in question or not asks_for_ranking:
        return None

    budget_pattern = re.compile(
        r"<td>\s*총예산\s*</td>\s*<td>\s*([0-9,]+)만 원\s*</td>"
        r"\s*<td>\s*([0-9,]+)만 원\s*</td>"
    )
    projects: dict[str, dict] = {}
    for chunk in engine.index["chunks"]:
        match = budget_pattern.search(chunk["text"])
        if not match:
            continue
        planned, actual = (int(value.replace(",", "")) for value in match.groups())
        candidate = {
            "rank": 1,
            "score": 0,
            "source_id": chunk["source_id"],
            "title": chunk["title"],
            "section_title": chunk["section_title"],
            "text": chunk["text"],
            "status": chunk["status"],
            "effective_date": chunk["effective_date"],
            "notion_url": chunk["notion_url"],
            "planned_budget": planned,
            "actual_budget": actual,
        }
        projects.setdefault(chunk["source_id"], candidate)

    if not projects:
        return None
    winner = max(
        projects.values(),
        key=lambda project: (project["actual_budget"], project["source_id"].startswith("ML-")),
    )
    return {
        "text": (
            f"예산이 가장 컸던 행사는 {winner['title']}입니다. "
            f"실제 총예산은 {winner['actual_budget']:,}만 원이었고, "
            f"계획 예산은 {winner['planned_budget']:,}만 원이었습니다."
        ),
        "source": winner,
        "comparison_count": len(projects),
    }


def generate_local_answer(question: str, results: list[dict]) -> str | None:
    """Generate a concise Korean answer using only retrieved source excerpts."""
    if os.getenv("MOMENTLAB_DISABLE_LLM") == "1":
        return None

    context = "\n\n".join(
        (
            f"[근거 {index}: {result['source_id']} · {result['section_title']}]\n"
            f"{result['text'][:900]}"
        )
        for index, result in enumerate(results[:3], start=1)
    )
    prompt = (
        "아래 조직 Context만 근거로 사용해 사용자의 질문에 한국어로 직접 답하세요. "
        "검색 문서나 Context를 나열하거나 읽어주지 말고, 결론을 첫 문장에 말하세요. "
        "근거에 없는 사실은 추측하지 말고 '확인 가능한 데이터가 없습니다.'라고 답하세요. "
        "질문을 충분히 해결할 만큼 설명하되, 불필요한 반복은 하지 마세요. "
        "필요하면 목록을 사용해도 됩니다.\n\n"
        f"질문: {question}\n\n{context}"
    )
    payload = json.dumps(
        {
            "model": OLLAMA_MODEL,
            "stream": False,
            "keep_alive": "0",
            "messages": [
                {
                    "role": "system",
                    "content": "당신은 근거 기반 조직 기억 챗봇입니다.",
                },
                {"role": "user", "content": prompt},
            ],
            "options": {"temperature": 0.1, "num_ctx": 4096, "num_predict": 240},
        }
    ).encode()
    request = Request(OLLAMA_CHAT_URL, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=90) as response:
            answer = json.load(response)["message"]["content"].strip()
    except (KeyError, OSError, URLError, json.JSONDecodeError):
        return None
    return answer or None


def build_answer(engine: ContextSearchEngine, question: str, response: dict) -> dict | None:
    budget_answer = find_budget_ranking_answer(engine, question)
    if budget_answer:
        return budget_answer
    if response["found"]:
        return {
            "text": generate_local_answer(question, response["results"])
            or extract_context_answer(question, response),
            "source": response["results"][0],
        }
    return None


st.title("🧠 MomentLab 조직 기억")
st.write("모먼트랩의 프로젝트·규정·업무 경험에서 관련 원문을 찾습니다.")
st.info(
    "로컬 AI가 검색된 Context를 바탕으로 질문에 직접 답합니다. "
    "근거가 없으면 답변을 만들지 않습니다."
)

with st.sidebar:
    st.subheader("현재 구현 상태")
    st.write("✅ Notion Context 변환")
    st.write("✅ 실행용 Context 검색")
    st.write("✅ 출처 표시")
    st.write("✅ 로컬 AI 답변 생성")
    st.divider()
    if st.button("대화 기록 지우기", use_container_width=True):
        st.session_state.history = []

if "history" not in st.session_state:
    st.session_state.history = []

try:
    engine = load_engine()
except (FileNotFoundError, ValueError) as exc:
    st.error(f"검색 데이터를 불러올 수 없습니다: {exc}")
    st.stop()

for exchange in reversed(st.session_state.history):
    with st.chat_message("user"):
        st.write(exchange["question"])
    with st.chat_message("assistant"):
        response = exchange["response"]
        answer = exchange.get("answer") or build_answer(engine, exchange["question"], response)
        if not response["found"] and not answer:
            st.markdown("#### 답변")
            st.write(response["message"])
            st.caption("질문을 뒷받침할 Context를 찾지 못했습니다.")
        else:
            if response["found"]:
                st.success(response["message"])
            primary_result = answer["source"]
            st.markdown("#### 답변")
            st.write(answer["text"])
            st.caption(
                "근거: "
                f"{primary_result['title']} · {primary_result['section_title']}"
            )
            if "comparison_count" in answer:
                st.caption(f"비교 범위: 총예산이 기록된 프로젝트 {answer['comparison_count']}건")
            st.caption("가장 관련도 높은 근거 원문입니다.")
            render_result_card(primary_result)

question = st.chat_input("예: 야외 행사에서 바람이 강할 때 어떻게 대응했어?")

if question is not None:
    cleaned_question = question.strip()
    if cleaned_question:
        response = engine.search(cleaned_question, top_k=5)
        st.session_state.history.append(
            {
                "question": cleaned_question,
                "response": response,
                "answer": build_answer(engine, cleaned_question, response),
            }
        )
        st.rerun()
    else:
        st.warning("질문을 입력해 주세요.")
