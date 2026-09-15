# 2단계: Notion Context JSON 변환

## 완료 범위

- 1단계에서 확인한 54개 페이지 중 변환 대상 48개를 읽기 전용으로 수집했다.
- 원문을 요약하거나 재작성하지 않고 Notion Markdown 본문을 보존했다.
- 실행용, 개발용, 평가용 데이터를 물리적으로 다른 JSON 파일로 분리했다.
- 혼합 문서는 제목 단위 허용 목록으로 나눴다. 알 수 없는 구역은 실행용이 아니라 개발용으로 분류한다.
- 원문 URL, Notion 최종 수정 시각, 경로, 검증 상태와 SHA-256 내용 해시를 기록했다.

## 산출물

| 파일 | 용도 | 실행 중 사용 |
| --- | --- | --- |
| `data/converted/runtime_documents.json` | 회사·프로젝트·규정·권한 Context | 사용 |
| `data/converted/development_documents.json` | 구현 설명·시연 문장·승인 전 초안 | 사용 안 함 |
| `data/converted/evaluation_documents.json` | 정답·채점·검증 문항 | 사용 안 함 |

## 안전 규칙

1. Notion 본문이 없으면 변환을 중단한다.
2. 누락된 내용을 AI나 기본 문장으로 채우지 않는다.
3. `후임자 확인`, `충돌 정답표`, `차단 정답`은 실행용 검색 데이터에서 제외한다.
4. 실행용 답변은 이후 단계에서도 `runtime_documents.json`만 검색해야 한다.
5. 각 내용의 해시가 달라지면 원문 변경 또는 변환 결과 변경으로 판단한다.

## 다시 변환하는 방법

```bash
uv run python scripts/build_context_corpus.py
```

이 명령은 이미 수집된 읽기 전용 Notion 스냅샷에서 JSON을 다시 생성한다. 실시간 Notion 동기화는 이후 단계의 기능이다.
