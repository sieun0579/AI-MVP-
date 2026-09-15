# MomentLab source inventory

## Snapshot

- Notion root: [AI 경영 학술제](https://app.notion.com/p/3cde19d6afb881f2a504d9b43b9a5037)
- Snapshot date: 2026-09-15
- Confirmed pages: 54
- Runtime sources: 37
- Evaluation-only sources: 3
- Development sources: 14
- Mixed pages requiring split: 5

## Inventory method

This inventory was built from the root page and the child-page references exposed by these verified Notion containers:

- [프로그램 Context](https://app.notion.com/p/3d8e19d6afb881148a00e7c4f131598d)
- [최종 통합 Context](https://app.notion.com/p/3dbe19d6afb881689359e9f1c4258e1f)
- [P-01~P-06 원천 상세 기록](https://app.notion.com/p/3dbe19d6afb8818091fae3fa541deebc)
- [모먼트랩 표준 업무 매뉴얼](https://app.notion.com/p/3dbe19d6afb88195bb0ffa15cc92851a)
- [MVP 구현 전 준비 패키지](https://app.notion.com/p/3dbe19d6afb8819f9d5fd6c48850fa38)

Leaf-page body conversion is intentionally deferred to stage 2. Empty metadata fields are preserved instead of guessed.

## Classification rules

- `runtime`: company knowledge eligible for later processing. Eligibility for retrieval still depends on status and access policy.
- `evaluation`: questions, expected labels, answer keys, scoring rules, and test fixtures. These must never enter the runtime retrieval corpus.
- `development`: plans, schemas, acceptance criteria, container pages, and mixed pages awaiting safe extraction.
- `requires_split`: the Notion page contains both runtime knowledge and evaluation/development content. Stage 2 must create separate records before ingestion.
- `excluded_from_runtime`: retained for traceability but excluded from chatbot retrieval.

## Important decisions

1. All 18 source projects remain traceable: ML-01~ML-12 and P-01~P-06.
2. U-01~U-12 remain separate integrated project records with explicit links to their source projects.
3. No source is deleted merely because its contents overlap.
4. PREP-01, PREP-04, and PREP-07 are mixed pages and cannot be ingested wholesale.
5. Q-01~Q-15 answers, capture labels, retrospective answers, and scoring data remain evaluation-only.
6. Approved organizational memories will be runtime data later; unapproved capture conversations remain workflow/evaluation inputs.

## Stage 2 handoff

Stage 2 should fetch each leaf body, extract runtime records from mixed pages, validate every converted record, and preserve the original Notion URL. It must not start until this inventory is approved.

