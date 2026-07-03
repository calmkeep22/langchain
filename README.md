# RAG Code Reviewer — 코드베이스 + 공식문서 기반 RAG 코드 리뷰 시스템

> **"이 코드, 공식문서 기준으로 봐도 괜찮은 거야?"**
> 내 프로젝트의 코드와 프레임워크 공식문서를 함께 검색해서, **근거가 있는** 코드 설명과 리뷰를 받습니다. 검색된 코드 위치와 문서 출처를 그대로 반환해 답변을 직접 검증할 수 있습니다.

<p>
  <a href="https://github.com/calmkeep22/langchain">
    <img alt="Stars" src="https://img.shields.io/badge/Stars-⭐️%20Give%20us%20a%20star!-brightgreen">
  </a>
  <a href="https://github.com/calmkeep22/langchain/pulls">
    <img alt="PRs Welcome" src="https://img.shields.io/badge/PRs-welcome-blue">
  </a>
  <a href="https://fastapi.tiangolo.com/">
    <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-backend-009688">
  </a>
  <a href="https://mistral.ai/">
    <img alt="Mistral" src="https://img.shields.io/badge/LLM-Mistral-orange">
  </a>
</p>

---

## 👀 한눈에 보기

* **코드 인덱싱**: 로컬 프로젝트 폴더를 함수/메서드 단위(AST 기반)로 쪼개서 벡터 저장소에 저장
* **공식문서 인덱싱**: Markdown 파일 또는 URL 크롤링으로 프레임워크 공식문서를 헤더 단위로 저장
* **하이브리드 검색**: Dense(임베딩) + BM25(키워드) 검색을 RRF로 결합해 코드/문서 근거를 찾음
* **질의 유형 라우팅**: 식별자 질문 / 구조·흐름 질문 / 일반 질문을 구분해 검색 파라미터를 조정
* **근거 기반 리뷰**: LLM이 검색된 코드·문서에만 근거해서 답변, 관련 코드 위치와 문서 출처를 함께 반환
* **구조화 로깅**: 모든 요청에 `request_id`를 부여하고 검색·LLM 호출 과정을 JSON 로그로 기록

---

## 💡 왜 RAG Code Reviewer인가?

* 일반 LLM은 내 프로젝트의 내부 코드를 모르고, 최신 공식문서와 다른 답변을 줄 수 있습니다.
* 코드 리뷰나 디버깅을 할 때 "이 기능이 어디서 처리되는지", "공식문서 기준으로 이 코드가 맞는지"를 확인하려면 코드/문서/에러 로그를 따로 뒤져야 합니다.
* RAG Code Reviewer는 코드베이스와 공식문서를 각각 인덱싱해두고, 질문마다 관련 근거를 검색해서 **그 근거를 기반으로만** 답변을 생성합니다. 근거가 부족하면 추측 대신 "근거 부족"이라고 답합니다.

---

## 🎯 핵심 사용 시나리오

**코드 흐름 설명**
```text
카메라 생성 API 흐름 설명해줘.
```
→ 관련 router, service, schema, model 코드를 검색해서 흐름을 설명합니다.

**공식문서 기준 코드 리뷰**
```text
이 JSONResponse 사용 방식 공식문서 기준으로 괜찮아?
```
→ 프로젝트 코드에서 JSONResponse 사용 위치와, 공식문서에서 관련 섹션을 함께 검색해 적절성을 판단합니다.

**에러 처리 검토**
```text
이 코드에서 예외 처리 구조가 괜찮아?
```
→ exception handler, service layer, 에러 코드 문서를 검색해 일관성을 검토합니다.

---

## 🔎 핵심 기능

### 1) 인덱싱 파이프라인

파일/URL 수집 → 전처리 → 청킹 → 메타데이터 구성 → 임베딩 순으로 처리합니다. Python 코드는 `ast` 모듈로 함수/메서드 단위 청킹(Small-to-Big)을, 공식문서는 Markdown 헤더 단위 청킹을 적용합니다.

<img width="298" height="548" alt="indexing-pipeline" src="https://github.com/user-attachments/assets/f41fe776-0830-404a-bf53-68907712ee61" />



### 2) 하이브리드 검색 (Dense + BM25 + RRF)

임베딩 유사도(Chroma) 검색과 BM25 키워드(SQLite FTS5) 검색을 각각 Top-20으로 수행한 뒤, Reciprocal Rank Fusion(k=60)으로 결합합니다. 같은 파일이 후보를 독점하지 않도록 파일당 최대 2개로 다양성을 제한합니다.

<img width="473" height="548" alt="hybrid-retrieval" src="https://github.com/user-attachments/assets/7b8e85f7-bec3-41cc-a120-d448a2435793" />

### 3) 질의 유형 분류 (Query Router)

질문을 `symbol`(식별자를 지목) / `architecture`(구조·흐름 질문) / `natural_language`(일반 질문)로 분류해, architecture 질문은 검색 범위를 넓히는 등 검색 파라미터를 조정합니다. LLM 호출 없이 규칙 기반으로 즉시 처리됩니다.

### 4) 근거 기반 리뷰 생성

검색된 코드/문서만을 근거로 LLM이 결론·관련 코드 위치·공식문서 근거·문제 설명·수정 방향·수정 예시를 포함한 리뷰를 생성합니다. 응답에는 실제 검색된 코드 위치(`related_code`)와 문서 출처(`official_references`)가 그대로 포함됩니다.


### 5) 구조화 로깅 및 요청 추적

모든 요청에 `request_id`가 부여되고, 검색된 chunk 수, 사용 모델, 지연 시간 등이 JSON 로그(`logs/app.log`)로 남습니다.

---

## 🗺️ 전체 아키텍처

<img width="765" height="548" alt="logical-architecture" src="https://github.com/user-attachments/assets/651cf731-c2c3-4999-a958-efc005417b4a" />

| 계층 | 구성 |
|---|---|
| API | FastAPI (`/api/projects`, `/api/index/code`, `/api/index/docs`, `/api/reviews`, `/api/retrievals`) |
| 검색 | Dense(Chroma) + BM25(SQLite FTS5) + RRF, Query Router |
| 생성 | Mistral(`ChatMistralAI`, structured output) |
| 저장 | Chroma(벡터), SQLite(메타데이터 + FTS5) |
| 로깅 | request_id 미들웨어, 구조화 JSON 로그 |

---

## 📈 검색 품질 평가

35개 한국어 질문 평가셋으로 코드 검색 품질을 지속적으로 측정하며 개선해왔습니다 (`eval/results.md`).

<img width="431" height="476" alt="evaluation-result" src="https://github.com/user-attachments/assets/079601d6-c087-4249-a566-3e6ea1ae5cd2" />

FlashRank 경량 reranker는 한국어 질문 + 영어 코드/한국어 주석이 섞인 이 코드베이스에서 오히려 성능을 크게 떨어뜨려(MRR 0.82 → 0.29~0.41) 기본값에서 비활성화했습니다. 자세한 실험 과정과 원인 분석은 `eval/results.md`에 모두 기록돼 있습니다.

---

## 🚀 빠른 시작

```bash
# 1. 의존성 설치
python -m venv .venv
source .venv/Scripts/activate  # Windows Git Bash 기준
pip install -r requirements.txt

# 2. 환경변수 설정
cp .env.example .env
# .env에 MISTRAL_API_KEY (또는 OPENAI_API_KEY) 입력

# 3. 서버 실행
uvicorn app.main:app --reload --reload-dir app
```

서버가 뜨면 `http://127.0.0.1:8000/docs`에서 Swagger UI로 바로 테스트할 수 있습니다.

**1) 프로젝트 등록**


**2) 코드 인덱싱**


**3) 리뷰 요청**

```json
POST /api/reviews
{
  "project_id": 1,
  "question": "카메라 생성 API 흐름 설명해줘"
}
```

---

## 📚 문서

프로젝트 설계 문서는 `docs/docs/`에 모두 정리돼 있습니다.

| 문서 | 내용 |
|---|---|
| [01-overview.md](docs/docs/01-overview.md) | 프로젝트 목적, 사용 시나리오, MVP 범위 |
| [02-requirements.md](docs/docs/02-requirements.md) | 기능/비기능 요구사항 |
| [03-architecture.md](docs/docs/03-architecture.md) | 시스템 아키텍처 |
| [04-api-spec.md](docs/docs/04-api-spec.md) | API 스펙 |
| [05-rag-pipeline.md](docs/docs/05-rag-pipeline.md) | 인덱싱/검색/프롬프트 파이프라인 상세 |
| [06-logging-policy.md](docs/docs/06-logging-policy.md) | 로깅 정책 |
| [07-error-code.md](docs/docs/07-error-code.md) | 에러 코드 |
| [08-database-schema.md](docs/docs/08-database-schema.md) | DB 스키마 |
| [09-demo-scenarios.md](docs/docs/09-demo-scenarios.md) | 데모 시나리오 |
| [10-troubleshooting.md](docs/docs/10-troubleshooting.md) | 트러블슈팅 |

---

## 🔐 데이터 및 보안

* API 키(`MISTRAL_API_KEY`, `OPENAI_API_KEY`)는 `.env`로 관리하며 저장소에 커밋하지 않습니다 (`.gitignore` 처리).
* 인덱싱된 코드/벡터/DB는 `data/` 디렉토리에 로컬로만 저장됩니다.
* 요청 로그는 `request_id` 기준으로 추적 가능하며 `logs/app.log`에 남습니다.

