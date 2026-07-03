# Retrieval Evaluation Log

## 코드 검색 평가

`eval/dataset.json` 기준, `eval/run_eval.py`로 측정한 결과 기록.

측정 대상: 이 저장소의 `app/` 폴더 (35개 질문, 파일 단위 정답 매칭)

| Version | 청킹 | 검색 | 후처리 | Hit@1 | Hit@3 | Recall@5 | MRR | 평균 지연 | p95 지연 |
|---|---|---|---|---|---|---|---|---|---|
| V1 (기록 당시 코드베이스, ~24 chunk) | RecursiveCharacterTextSplitter (1200/200) | Dense (Mistral), search_k=5 | 없음 | 0.829 (29/35) | 0.943 (33/35) | 0.943 (33/35) | 0.886 | 460 ms | 853 ms |

지연 시간은 질문 1건당 임베딩 API 호출 + Chroma 검색을 합친 시간이며, 대부분 Mistral 임베딩 API 네트워크 왕복 시간이 차지한다.

### 실행 방법

```bash
python eval/run_eval.py --label V1
```

`.env`에 `MISTRAL_API_KEY` 또는 `OPENAI_API_KEY`가 설정되어 있어야 한다.

### V1 관찰 사항

35개 중 2개 MISS, 둘 다 짧고 심볼 정보가 없는 파일이 대상일 때 발생했다.

- ".venv, __pycache__ 제외 디렉토리" 질문 → `code_loader.py` 대신 `code_indexing_service.py`가 1위로 검색됨
- "서버 시작 시 SQLite 테이블 생성" 질문 → `main.py` 대신 테이블 정의가 있는 model 파일들이 상위로 검색됨

두 경우 모두 파일 하나가 통째로 하나의 chunk가 되면서, 그 안에서 어떤 부분이 질문과 관련 있는지 구분이 안 되는 게 원인으로 보인다.

---

## V2: AST 기반 코드 청킹 (#13) — 공정 비교로 재측정

### 측정 방법의 함정과 수정

V2(AST 함수/메서드 단위 청킹) 적용 후 처음 측정했을 때 `search_k=5`로 V1과 그대로 비교했더니 Hit@1 0.829→0.771, MRR 0.886→0.833으로 **하락**한 것처럼 보였다. 두 가지 이유로 이 비교는 잘못됐다.

1. **eval 데이터셋은 파일 단위로 정답을 매칭하는데, AST 청킹은 파일 하나당 chunk 수가 훨씬 많아진다.** `search_k=5`로 raw 후보를 5개만 뽑으면, 같은 파일에서 나온 여러 chunk가 top-5 슬롯을 나눠 차지해서 실제로 비교 대상이 되는 파일 종류 자체가 줄어든다. `eval/run_eval.py`에 `--search-k`(기본 20) 옵션을 추가해 raw 후보를 더 넓게 뽑은 뒤 파일 단위로 dedup하도록 고쳤다.
2. **기록해둔 V1 수치(0.886 MRR)는 코드베이스가 훨씬 작았을 때(24 chunk) 측정한 것**이라, 그 사이 이슈 #4~#13이 merge되며 커진 지금 코드베이스(70+ chunk)와 비교하는 것 자체가 불공정했다.

두 가지를 모두 통제해서(같은 코드베이스 스냅샷, 같은 `search_k=20` eval) 다시 측정한 결과:

| Version | 청킹 | Hit@1 | Hit@3 | Recall@5 | MRR |
|---|---|---|---|---|---|
| V1-fixed-eval (현재 코드베이스) | 파일 단위 (1200/200) | 0.771 | 0.914 | 0.943 | 0.848 |
| V2-fixed-eval (현재 코드베이스) | AST 함수/메서드 단위 (#13) | 0.771 | 0.943 | 0.971 | 0.856 |

같은 조건에서 비교하면 **AST 청킹이 모든 지표에서 동등하거나 더 좋다.** 처음의 "AST가 더 나쁘다"는 결론은 측정 방법 결함(좁은 search_k) + 부적절한 baseline(다른 시점 코드베이스) 때문이었다.

### 남은 한계 (측정과 무관하게 실제로 남아있는 문제)

- **Small-to-Big은 retrieval 지표에 반영되지 않는다.** 검색이 끝난 뒤 LLM 컨텍스트를 넓히는 단계라서, 여기 있는 Hit@k/MRR로는 효과를 확인할 수 없다. 실제 검증은 `UsersRepository` 같은 클래스+메서드 샘플로 프롬프트에 클래스 전체가 들어가는 것을 직접 확인했다 (review_service._build_code_context).
- **긴 top-level 함수는 Small-to-Big의 혜택을 못 받는다.** parent 확장은 클래스의 메서드에만 적용되고, `index_project_code`처럼 긴 top-level 함수가 `MAX_SYMBOL_CHUNK_SIZE`(4000자)로 재분할되면 하위 조각들에 parent 연결이 없다.
- **모듈 레벨 chunk(import 등)의 임베딩 텍스트가 빈약할 수 있다.** 코드만 놓고 보면 문맥(어떤 기능의 일부인지)이 부족해서 검색 신호가 약할 수 있다.
- **파일 다양성**: 같은 파일에서 여러 chunk가 나올 수 있어 top-k가 한 파일에 쏠릴 수 있다 (이번에 eval 스크립트에서는 dedup으로 우회했지만, 실제 리뷰 API의 검색 결과에는 아직 적용 안 됨 — 이슈 #16에서 다룰 예정).

---

## V3: Dense + BM25 하이브리드 검색 (#14)

SQLite FTS5(`chunk_fts`)로 BM25 키워드 검색을 추가하고, Dense Top-20 + BM25 Top-20을 Reciprocal Rank Fusion(RRF, k=60)으로 결합했다. `eval/run_eval.py --hybrid` 옵션으로 측정.

| Version | 검색 | Hit@1 | Hit@3 | Recall@5 | MRR |
|---|---|---|---|---|---|
| V2-fixed-eval | Dense만 | 0.771 | 0.943 | 0.971 | 0.856 |
| V3 (하이브리드, RRF k=60) | Dense + BM25 | 0.714 | 0.886 | 0.971 | 0.823 |

### 좋아진 점

Dense 검색으로는 완전히 놓쳤던 질문("임베딩 설정 오류를 502 에러로 변환하는 로직은?")을 BM25가 `EMBEDDING_FAILED`/`502` 키워드로 정확히 잡아내서 1위로 찾아냈다. Recall@5는 V2와 동일(0.971)하게 유지됐다 — 아예 못 찾는 케이스가 늘지는 않았다.

### 나빠진 점과 원인

Hit@1(0.771→0.714), MRR(0.856→0.823)이 하락했다. `rrf_k`를 30~300까지 바꿔가며 테스트했지만 전혀 회복되지 않았다:

```text
rrf_k= 30  hit@1=0.714  hit@3=0.914  recall@5=0.971  mrr=0.826
rrf_k= 60  hit@1=0.714  hit@3=0.886  recall@5=0.971  mrr=0.823
rrf_k=100  hit@1=0.714  hit@3=0.886  recall@5=0.971  mrr=0.823
rrf_k=150  hit@1=0.714  hit@3=0.886  recall@5=0.971  mrr=0.823
rrf_k=200  hit@1=0.714  hit@3=0.886  recall@5=0.971  mrr=0.823
rrf_k=300  hit@1=0.714  hit@3=0.886  recall@5=0.971  mrr=0.823
```

이건 파라미터 튜닝으로 해결되는 문제가 아니라 RRF의 구조적 특성 때문이다. RRF는 "어느 한쪽에서 1등인 문서"보다 "dense와 BM25 양쪽에 모두 등장하는 문서"에 유리하다 — 두 리스트에 다 있으면 점수가 합산되기 때문에, dense 단독 1위보다 양쪽에 중간 순위로 걸치는 문서가 역전할 수 있다. `k`를 아무리 키워도 이 "이중 등장 보너스" 자체는 사라지지 않는다.

`RRF_K`는 문헌상 표준값인 60을 그대로 사용하기로 했다 (k=30이 근소하게 나았지만 차이가 노이즈 수준).

### 다음 비교 대상

- V4: V3 + Reranking (#15) — RRF로 넓게 후보를 모은 뒤 reranker로 재정렬하면 이번에 하락한 Hit@1을 회복할 가능성이 높다
- V5: V4 + 파일 다양성 조정 (#16)

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
