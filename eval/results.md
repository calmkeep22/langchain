# Retrieval Evaluation Log

## 코드 검색 평가

`eval/dataset.json` 기준, `eval/run_eval.py`로 측정한 결과 기록.

측정 대상: 이 저장소의 `app/` 폴더 (35개 질문, 파일 단위 정답 매칭)

| Version | 청킹 | 검색 | 후처리 | Hit@1 | Hit@3 | Recall@5 | MRR | 평균 지연 | p95 지연 |
|---|---|---|---|---|---|---|---|---|---|
| V1 | RecursiveCharacterTextSplitter (1200/200) | Dense (Mistral) | 없음 | 0.829 (29/35) | 0.943 (33/35) | 0.943 (33/35) | 0.886 | 460 ms | 853 ms |

지연 시간은 질문 1건당 임베딩 API 호출 + Chroma 검색을 합친 시간이며, 대부분 Mistral 임베딩 API 네트워크 왕복 시간이 차지한다. 하이브리드 검색/reranking을 추가하면 정확도와 함께 이 수치도 반드시 같이 비교해야 한다.

### 실행 방법

```bash
python eval/run_eval.py --label V1
```

`.env`에 `MISTRAL_API_KEY` 또는 `OPENAI_API_KEY`가 설정되어 있어야 한다.

### V1 관찰 사항

35개 중 2개 MISS, 둘 다 짧고 심볼 정보가 없는 파일이 대상일 때 발생했다.

- ".venv, __pycache__ 제외 디렉토리" 질문 → `code_loader.py` 대신 `code_indexing_service.py`가 1위로 검색됨
- "서버 시작 시 SQLite 테이블 생성" 질문 → `main.py` 대신 테이블 정의가 있는 model 파일들이 상위로 검색됨

두 경우 모두 파일 하나가 통째로 하나의 chunk가 되면서, 그 안에서 어떤 부분이 질문과 관련 있는지 구분이 안 되는 게 원인으로 보인다. AST 기반 심볼 단위 청킹(#13)이 이 문제를 직접 해결할 가능성이 높다.

### 다음 비교 대상

- V2: AST 기반 Python 청킹 + fallback (#13)
- V3: Dense + BM25 하이브리드 검색 (#14)
- V4: V3 + Reranking (#15)
- V5: V4 + Parent 컨텍스트 확장 (#13, Small-to-Big)

---

## 공식문서(URL) 검색 평가

`eval/docs_dataset.json` 기준, `eval/run_docs_eval.py`로 측정한 결과 기록.

측정 대상: `https://fastapi.tiangolo.com/ko/learn/`에서 `max_depth=2`로 실제 크롤링한 FastAPI 한국어 공식문서 전체 (150개 페이지, 3,962 chunk), 25개 질문, 문서(URL) 단위 정답 매칭

| Label | 페이지 수 | Chunk 수 | Hit@1 | Hit@3 | Recall@5 | MRR |
|---|---|---|---|---|---|---|
| docs-full-150 | 150 | 3,962 | 0.720 (18/25) | 1.000 (25/25) | 1.000 (25/25) | 0.853 |

인덱싱 소요 시간: 약 8분 12초 (실제 Mistral 임베딩 API 호출 포함, 150페이지 크롤링+청킹+임베딩+저장 전체).

### 실행 방법

```bash
# 1. 문서 인덱싱 (사전에 한 번, 시간 오래 걸림)
curl -X POST http://localhost:8000/api/index/docs -H "Content-Type: application/json" -d '{"doc_name":"fastapi-ko-full","url":"https://fastapi.tiangolo.com/ko/learn/","max_depth":2}'

# 2. 검색 품질 측정 (이미 인덱싱된 데이터 대상)
python eval/run_docs_eval.py --label docs-full-150
```

### 구현 과정에서 발견하고 고친 문제

- **네비게이션 잡음**: 페이지 전체를 `html2text`로 변환하면 사이드바 메뉴, 스폰서 배너, 언어 선택 링크까지 chunk로 들어갔다 (테스트 페이지 기준 전체 chunk의 약 30%). `<article>`/`<main>` 태그로 본문만 추출하도록 고쳤다.
- **코드 주석의 헤더 오인식**: `html2text`는 코드 블록을 4-space 들여쓰기로만 표현하는데, `MarkdownHeaderTextSplitter`는 이걸 코드 블록으로 인식하지 못해서 코드 예제 안의 주석(`# Don't do this in production!`)을 실제 h1 헤더로 잘못 인식했다. 그 결과 그 이후 모든 섹션의 h1 metadata가 코드 주석으로 덮어써지는 버그가 있었다. `html2text`의 `mark_code` 옵션으로 코드 블록을 표시한 뒤 진짜 ` ``` ` fenced code block으로 변환하는 전처리를 추가해 해결했다 (`MarkdownHeaderTextSplitter`는 fenced code block 내부의 `#`는 헤더로 인식하지 않음).
- **크롤링 범위**: `prevent_outside`만으로는 다국어 문서 사이트에서 `/ko/` 페이지가 `/en/`, `/de/` 등 다른 언어 섹션까지 크롤링하는 것을 막지 못했다. 시작 URL의 최상위 경로 segment(`base_url`)로 범위를 제한해 해결했다.
- **페이지 수 상한**: 초기 40페이지였던 안전 상한을 150으로 올렸다 — FastAPI `/ko/` 문서 전체가 150페이지보다 많아서 이번 측정도 상한에 걸려 잘렸다 (전체를 다 가져오려면 상한을 더 올려야 한다).
