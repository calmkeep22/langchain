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

---

## V4: Reranking (#15) — 채택하지 않음

RRF Top-20 후보를 FlashRank 경량 cross-encoder로 재정렬해서 V3에서 떨어진 Hit@1을 회복하려 했다. 결과는 회복은커녕 큰 폭으로 더 나빠졌다.

| Version | Reranker | Hit@1 | Hit@3 | Recall@5 | MRR | 평균 지연 |
|---|---|---|---|---|---|---|
| V3 | 없음 | 0.714 | 0.886 | 0.971 | 0.823 | ~900 ms |
| V4a | ms-marco-TinyBERT-L-2-v2 | 0.029 | 0.457 | 0.714 | 0.289 | ~1060 ms |
| V4b | ms-marco-MiniLM-L-12-v2 | 0.200 | 0.571 | 0.686 | 0.413 | ~5790 ms |

### 원인

`services/review_service.py`의 LLM 프롬프트 템플릿 chunk(`PROMPT_TEMPLATE` — `[사용자 질문]`, `{question}`, `관련 코드` 같은 한국어 placeholder 텍스트를 담은 코드)가 질문 주제와 전혀 무관한데도 거의 모든 질문에서 0.99에 가까운 점수를 받아 상위를 독점했다. TinyBERT(영어 전용)뿐 아니라 다국어 모델(MultiBERT), 더 큰 모델(MiniLM-L-12)까지 같은 실패 패턴을 보였다 — 특정 모델의 결함이 아니라, 지금 시도한 FlashRank 경량 reranker들 전반이 "한국어 질문 + 영어 코드/한국어 docstring·프롬프트가 섞인 코드베이스" 조합에 안정적으로 대응하지 못하는 것으로 보인다. 프롬프트 템플릿처럼 "질문"/"코드" 같은 메타 어휘를 담은 텍스트가 실제 내용과 무관하게 높은 점수를 받는 표면적 패턴 매칭 실패로 추정된다.

### 결정

reranking 코드(`app/core/reranker.py`, `hybrid_search.py`의 `use_reranking`)는 남겨두되 **기본값을 `False`로 꺼둔다**. 실제 서비스는 V3(RRF까지만)로 동작한다. 더 나은 reranker(다국어 특화 모델, LLM 기반 relevance scoring 등)를 나중에 검토할 수 있도록 opt-in 구조는 유지한다.

### 다음 비교 대상

- V5: 검색 결과 파일 다양성 조정 (#16)
- 향후: LLM 기반 reranking 또는 더 큰/특화된 cross-encoder 재검토

---

## V5: 검색 결과 파일 다양성 조정 (#16)

RRF 순위 리스트에서 같은 파일의 chunk가 후보 풀(`RERANK_POOL=20`)을 독점하지 못하도록 `diversify_by_file(max_per_file=2)`를 추가했다.

| Version | Hit@1 | Hit@3 | Recall@5 | MRR |
|---|---|---|---|---|
| V3 (다양성 조정 전) | 0.714 | 0.886 | 0.971 | 0.823 |
| V5 (다양성 조정 후, `--no-rerank`) | 0.714 | 0.886 | 0.971 | 0.823 |

파일 단위 eval 지표는 그대로다 — `eval/run_eval.py`가 애초에 파일 단위로 dedup해서 채점하기 때문에, 후보 풀 단계의 다양성 조정은 이 지표에 잡히지 않는다. 대신 실제 후보 풀 구성을 직접 비교해서 효과를 확인했다.

질문: "코드 인덱싱 로직 전체 흐름 설명해줘" (top-6 후보)

```text
다양성 없음 (max_per_file=None):
  services/review_service.py        x3 (None, ReviewAnswer, _build_code_context)
  services/code_indexing_service.py x2 (index_project_code 중복 포함)
  → 파일 2종류만 등장

다양성 적용 (max_per_file=2, 기본값):
  services/review_service.py        x2
  services/code_indexing_service.py x2
  core/fts.py                       x1  (새로 등장)
  api/index.py                      x1  (새로 등장)
  → 파일 4종류 등장
```

리뷰 API가 LLM에 전달하는 근거의 파일 다양성이 실제로 개선됐다. 특정 파일을 명확히 지목한 질문에는 `max_per_file=None`으로 제한을 끌 수 있도록 파라미터화해뒀다 (질의 유형 분류, #17에서 활용 예정).

---

## V6: 질의 유형 분류 및 Query Router (#17)

질문을 `symbol`/`architecture`/`natural_language` 세 유형으로 분류해 `dense_weight`/`sparse_weight`/`top_k`를 조정하는 규칙 기반 라우터를 추가했다. `eval/dataset.json`은 대부분(33/35) `natural_language`로 분류되어 기존과 동일한 파라미터를 받으므로, 회귀가 없는지 확인하는 것이 이번 측정의 목적이다.

| Version | Hit@1 | Hit@3 | Recall@5 | MRR |
|---|---|---|---|---|
| V5 (Query Router 적용 전) | 0.714 | 0.886 | 0.971 | 0.823 |
| V6 (Query Router 적용 후, `--hybrid --no-rerank`) | 0.714 | 0.886 | 0.971 | 0.822 |

지표 동일 (MRR 0.001 차이는 반올림). 이 eval 세트로는 라우팅 자체의 효과를 측정할 수 없으므로 — symbol 질문 2개뿐이고 architecture 질문은 0개 — 분류 결과와 파라미터 변화를 직접 확인했다.

```text
"force_reindex 옵션은 어디서 처리해?"        → symbol            (sparse_weight=2.0, V7에서 1.0으로 변경됨 — 아래 참고)
"코드 인덱싱 전체 흐름 설명해줘"              → architecture      (top_k_multiplier=2)
"임베딩 API 키가 없을 때 발생하는 예외는?"    → natural_language  (기본값 그대로)
```

symbol 분류 정규식에서 `API`, `POST`, `JSON` 같은 일반 약어가 `ALL_CAPS` 패턴에 걸려 오탐되는 문제가 있었다 (35개 중 8개가 symbol로 잘못 분류됨). 패턴에 언더스코어(`_`)를 필수로 요구하도록 수정해 오탐을 2개로 줄였다 (`code_chunks`, `force_reindex`처럼 실제 식별자를 지목한 정상 케이스만 남음).

---

## V7: BM25 토크나이저 버그 수정 및 symbol 가중치 원복 (#29)

실사용 테스트 중 `"response_model이랑 response_class 차이가 뭐야?"` 질문에서 실제로 인덱싱된 `tutorial/response-model/` 문서가 전혀 검색되지 않고, LLM이 검색 결과에도 없는 출처(`.../advanced/custom-response/#response-class`)를 답변에 지어내는 사례를 발견했다.

**원인 1 — 토큰 뭉침 버그**: `app/core/fts.py`의 토큰 정규식 `[\w가-힣]+`는 Python 정규식에서 `\w`가 한글도 포함하기 때문에, 영어 식별자에 조사가 공백 없이 붙으면(`response_model이랑`) 하나의 토큰으로 뭉쳐 실제 문서에 없는 검색어가 돼버린다. `[A-Za-z0-9_]+|[가-힣]+`로 스크립트 경계에서 분리하도록 수정했다.

**원인 2 — symbol 라우팅의 부작용**: 토크나이저를 고쳐도 이 질문은 여전히 실패했다. 원인은 `이랑`/`차이가`/`뭐야` 같은 조사·의문사 토큰이 코퍼스 전체에서 희귀해서 BM25 IDF상 `response_model`보다 더 높은 점수를 받기 때문이다. Query Router가 이 질문을 `symbol`로 분류해 `sparse_weight=2.0`을 적용하면서 이 노이즈가 오히려 증폭됐다.

| 가중치 | 검색 결과 (공식문서 top-5) |
|---|---|
| `sparse_weight=1.0` (라우팅 없음 가정) | async, **response-model**, reference, **response-model**, reference — 근처에 있음 |
| `sparse_weight=2.0` (V6 symbol 라우팅) | async, reference, reference, apirouter, apirouter — response-model 탈락 |
| `sparse_weight=1.0` (V7, symbol 원복 후) | async, **response-model**, reference, **response-model**, reference — 라우팅 없음과 동일 |

한국어 조사를 제대로 떼어내려면 형태소 분석기가 필요해 이번 범위를 벗어난다고 판단해, symbol 질의의 `sparse_weight`를 1.0으로 되돌려 당장의 역효과만 제거했다.

| Version | Hit@1 | Hit@3 | Recall@5 | MRR |
|---|---|---|---|---|
| V6 (symbol sparse_weight=2.0) | 0.714 | 0.886 | 0.971 | 0.822 |
| V7 (토크나이저 수정 + symbol sparse_weight=1.0) | 0.714 | 0.914 | 0.971 | 0.820 |

코드 검색 eval 지표 기준으로는 회귀 없음 (오히려 Hit@3 소폭 개선, MRR 차이는 반올림 오차 수준). 형태소 분석 기반 토크나이징은 후속 과제로 남겨둔다.

**원인 3 — LLM이 근거 없는 출처를 지어냄**: 검색 자체를 고친 뒤에도, `_build_doc_context()`가 LLM 컨텍스트에 `doc_name`과 섹션 제목만 넣고 **실제 URL(`source`)을 아예 포함하지 않았다는 사실**을 발견했다. LLM은 URL을 본 적이 없으니 FastAPI 문서 구조에 대한 자기 지식으로 그럴듯한 URL을 재구성했고, 그 결과 실제로 검색되지 않은 페이지(`custom-response`)를 근거인 것처럼 인용하거나, 검색된 URL의 경로를 미묘하게 틀리게(`/tutorial/` 누락) 답변에 적었다.

수정: `_build_doc_context()`의 컨텍스트 블록에 `URL: {source}` 줄을 추가하고, `PROMPT_TEMPLATE`에 "URL은 [관련 공식문서]에 적힌 그대로 사용하고, 없는 URL은 쓰지 마라"는 지시를 추가했다. 수정 후 같은 질문으로 재검증한 결과, 답변에 인용된 URL이 `official_references`에 실제로 있는 URL과 정확히 일치했다(섹션 앵커 `#...`만 추가된 정도는 같은 페이지를 가리키므로 문제 없음).

**참고 — RRF 점수 스케일에 대한 오해 방지**: 위 검증 과정에서 `related_code`/`official_references`의 `score`가 0.015~0.03 정도로 낮게 나오는 것을 보고 "유사도가 낮은 것 아니냐"는 질문이 나왔는데, 이 값은 코사인 유사도가 아니라 RRF 점수(`weight / (k + rank)`, `k=60`)다. 한쪽 검색에서만 1등을 해도 최대 `1/61 ≈ 0.0164`이므로 이 스케일이 정상이며, 실제 관련성과 직접 비례하지 않는다 (V3 참고).

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
