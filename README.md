# MomentLab 조직 기억 챗봇

모먼트랩의 Notion Context를 로컬 JSON으로 변환하고, 실행용 자료만 검색해 브라우저에서 원문 근거를 확인하는 1차 MVP다.

## 현재 기능

- Notion Context 출처 목록 및 읽기 전용 스냅샷
- 실행용·개발용·평가용 데이터 분리
- 긴 문서의 검색 조각 생성
- 한국어 키워드 및 프로젝트 ID 검색
- 원문·문서명·상태·Notion 출처 표시
- 근거가 없을 때 `확인 가능한 데이터가 없습니다.` 출력
- Streamlit 기반 브라우저 채팅 화면

현재 버전은 로컬 LLM을 연결하지 않았으며 자연어 답변을 생성하지 않는다.

## macOS에서 실행

프로젝트 폴더를 VS Code로 연 뒤 터미널에서 실행한다.

```bash
uv sync --group dev
uv run streamlit run app.py
```

터미널에 표시되는 `http://localhost:8501` 주소를 브라우저에서 연다.

## 테스트

```bash
uv run pytest
```

## 주요 폴더

- `app.py`: 브라우저 화면
- `src/momentlab_context/`: Context 변환·검색 기능
- `data/converted/`: 범위별 변환 JSON
- `data/search/`: 실행용 검색 색인
- `scripts/`: 변환·색인·터미널 검색 명령
- `tests/`: 자동 테스트
- `docs/`: 단계별 구현 설명

## 아직 지원하지 않는 기능

- `이거`, `저번 행사` 같은 대화 지시어 해석
- 예산·기간 등의 구조화 조건 검색
- 사용자 역할별 권한 필터
- 자연어 답변 생성과 로컬 LLM
- 새로운 조직 기억의 저장·승인
