# 09. Demo Scenarios

## 1. 문서 목적

이 문서는 RAG Code Reviewer의 데모 시나리오를 정의합니다.

초기 버전은 별도 UI 없이 Swagger UI, curl, Postman을 사용해 데모합니다.

---

## 2. 데모 전제

서버 실행:

```bash
uvicorn app.main:app --reload
```

Swagger UI:

```text
http://localhost:8000/docs
```

샘플 데이터:

```text
data/sample_projects/fastapi_app
data/official_docs/fastapi_response.md
data/official_docs/pydantic_model.md
```

---

## 3. Scenario 1. 프로젝트 등록

### 목적

분석 대상 코드 프로젝트를 등록합니다.

### Request

```bash
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "sample-fastapi-project",
    "root_path": "./data/sample_projects/fastapi_app"
  }'
```

### Expected Response

```json
{
  "success": true,
  "data": {
    "project_id": 1,
    "name": "sample-fastapi-project",
    "root_path": "./data/sample_projects/fastapi_app"
  },
  "request_id": "req_abc123"
}
```

### 확인 포인트

- request_id가 응답에 포함되는가?
- 잘못된 경로 입력 시 INVALID_PROJECT_PATH가 반환되는가?
- 요청 로그가 남는가?

---

## 4. Scenario 2. 코드 인덱싱

### 목적

등록된 프로젝트의 코드 파일을 인덱싱합니다.

### Request

```bash
curl -X POST http://localhost:8000/api/index/code \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": 1,
    "force_reindex": false
  }'
```

### Expected Response

```json
{
  "success": true,
  "data": {
    "project_id": 1,
    "indexed_files": 12,
    "indexed_chunks": 58,
    "skipped_files": 3,
    "status": "COMPLETED"
  },
  "request_id": "req_abc123"
}
```

### 확인 포인트

- `.git`, `.venv`, `__pycache__`가 제외되는가?
- Chroma에 code chunk가 저장되는가?
- documents, chunks metadata가 SQLite에 저장되는가?
- code_indexing_completed 로그가 남는가?

---

## 5. Scenario 3. 공식문서 인덱싱

### 목적

FastAPI 공식문서 Markdown 파일을 인덱싱합니다.

### Request

```bash
curl -X POST http://localhost:8000/api/index/docs \
  -H "Content-Type: application/json" \
  -d '{
    "doc_name": "fastapi-response-docs",
    "source_type": "official_doc",
    "path": "./data/official_docs/fastapi_response.md"
  }'
```

### Expected Response

```json
{
  "success": true,
  "data": {
    "document_id": 3,
    "doc_name": "fastapi-response-docs",
    "indexed_chunks": 18,
    "status": "COMPLETED"
  },
  "request_id": "req_abc123"
}
```

### 확인 포인트

- Markdown header 기준으로 chunk가 분할되는가?
- source, h1, h2 metadata가 저장되는가?
- docs_indexing_completed 로그가 남는가?

---

## 6. Scenario 4. FastAPI Response 코드 리뷰

### 목적

사용자 코드에서 Response 반환 방식이 공식문서 기준으로 적절한지 검토합니다.

### Request

```bash
curl -X POST http://localhost:8000/api/reviews \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": 1,
    "question": "이 JSONResponse 사용 방식 공식문서 기준으로 괜찮아?",
    "code_top_k": 5,
    "doc_top_k": 5
  }'
```

### Expected Response

```json
{
  "success": true,
  "data": {
    "review_id": 10,
    "verdict": "PROBLEM",
    "answer": "현재 코드는 Pydantic 모델을 JSONResponse에 직접 전달하고 있어 문제가 될 수 있습니다...",
    "related_code": [
      {
        "file_path": "app/api/events.py",
        "symbol_name": "create_event_response",
        "start_line": 31,
        "end_line": 47,
        "score": 0.82
      }
    ],
    "official_references": [
      {
        "title": "Use jsonable_encoder in a Response",
        "source": "fastapi_response.md",
        "section": "JSON Compatible Encoder",
        "score": 0.79
      }
    ],
    "latency_ms": 2840
  },
  "request_id": "req_abc123"
}
```

### 확인 포인트

- 관련 코드 chunk가 검색되는가?
- 공식문서 chunk가 검색되는가?
- 답변이 검색 근거에 기반하는가?
- 근거 부족 시 추측하지 않는가?
- rag_review_completed 로그가 남는가?

---

## 7. Scenario 5. API 흐름 설명

### 목적

코드베이스 기준으로 특정 API 흐름을 설명합니다.

### Request

```bash
curl -X POST http://localhost:8000/api/reviews \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": 1,
    "question": "카메라 생성 API 흐름 설명해줘."
  }'
```

### Expected Result

답변에는 다음 내용이 포함되어야 합니다.

- 요청을 받는 router 또는 controller
- 요청 schema
- service 함수
- DB model 또는 repository
- 예외 처리 흐름
- 관련 파일 경로

---

## 8. Scenario 6. 에러 처리 검토

### 목적

프로젝트의 예외 처리 방식이 일관적인지 검토합니다.

### Request

```bash
curl -X POST http://localhost:8000/api/reviews \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": 1,
    "question": "이 프로젝트의 예외 처리 구조에서 개선할 점 찾아줘."
  }'
```

### Expected Result

답변에는 다음 내용이 포함될 수 있습니다.

- service layer에서 ValueError를 직접 던지는지 여부
- custom exception 사용 여부
- exception handler 존재 여부
- error code 문서와 실제 구현 일치 여부

---

## 9. Scenario 7. 검색 근거 조회

### 목적

특정 리뷰 요청에서 실제 검색된 chunk를 확인합니다.

### Request

```bash
curl -X GET http://localhost:8000/api/retrievals/10
```

### Expected Response

```json
{
  "success": true,
  "data": {
    "review_id": 10,
    "retrieved_chunks": [
      {
        "rank": 1,
        "source_type": "code",
        "source": "app/api/events.py",
        "score": 0.82,
        "preview": "def create_event_response(...):"
      }
    ]
  },
  "request_id": "req_abc123"
}
```

### 확인 포인트

- LLM 답변의 근거가 실제 검색 결과와 일치하는가?
- score와 rank가 저장되는가?
- 검색 결과가 너무 엉뚱하지 않은가?

---

## 10. 데모 성공 기준

데모는 다음 조건을 만족하면 성공으로 봅니다.

1. 프로젝트 등록이 가능하다.
2. 코드 인덱싱이 가능하다.
3. 공식문서 인덱싱이 가능하다.
4. 리뷰 질문에 대해 답변이 생성된다.
5. 답변에 관련 코드와 공식문서 근거가 포함된다.
6. request_id가 모든 응답에 포함된다.
7. 구조화 로그가 출력된다.
8. Swagger UI에서 API 사용 흐름을 재현할 수 있다.
