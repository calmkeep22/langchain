# 04. API Specification

## 1. 문서 목적

이 문서는 RAG Code Reviewer의 주요 API 명세를 정의합니다.

초기 버전은 FastAPI Swagger UI에서 테스트 가능한 REST API를 기준으로 합니다.

---

## 2. 공통 응답 형식

### 2.1 성공 응답

```json
{
  "success": true,
  "data": {},
  "request_id": "req_abc123"
}
```

### 2.2 실패 응답

```json
{
  "success": false,
  "error": {
    "code": "PROJECT_NOT_FOUND",
    "message": "Project not found."
  },
  "request_id": "req_abc123"
}
```

---

## 3. 공통 헤더

| Header | Required | Description |
|---|---|---|
| X-Request-ID | No | 클라이언트가 직접 지정하는 요청 추적 ID |
| Content-Type | Yes | `application/json` |

`X-Request-ID`가 없으면 서버에서 UUID 기반으로 생성합니다.

---

## 4. Health API

### GET /api/health

서버 상태를 확인합니다.

#### Response

```json
{
  "success": true,
  "data": {
    "status": "UP",
    "service": "rag-code-reviewer"
  },
  "request_id": "req_abc123"
}
```

---

## 5. Project API

### POST /api/projects

분석 대상 프로젝트를 등록합니다.

#### Request

```json
{
  "name": "sample-fastapi-project",
  "root_path": "./data/sample_projects/fastapi_app"
}
```

#### Response

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

#### Errors

| Code | Status | Description |
|---|---:|---|
| INVALID_PROJECT_PATH | 400 | 프로젝트 경로가 존재하지 않음 |
| PROJECT_ALREADY_EXISTS | 409 | 동일 이름 프로젝트가 이미 존재함 |

---

### GET /api/projects/{project_id}

프로젝트 정보를 조회합니다.

#### Response

```json
{
  "success": true,
  "data": {
    "project_id": 1,
    "name": "sample-fastapi-project",
    "root_path": "./data/sample_projects/fastapi_app",
    "created_at": "2026-07-01T12:00:00"
  },
  "request_id": "req_abc123"
}
```

#### Errors

| Code | Status | Description |
|---|---:|---|
| PROJECT_NOT_FOUND | 404 | 프로젝트를 찾을 수 없음 |

---

### GET /api/projects

등록된 프로젝트 목록을 조회합니다 (UI의 프로젝트 선택 목록용, #32).

#### Response

```json
{
  "success": true,
  "data": [
    {
      "project_id": 1,
      "name": "sample-fastapi-project",
      "root_path": "./data/sample_projects/fastapi_app"
    }
  ],
  "request_id": "req_abc123"
}
```

---

## 6. Indexing API

### POST /api/index/code

프로젝트 코드를 인덱싱합니다.

#### Request

```json
{
  "project_id": 1,
  "force_reindex": false
}
```

#### Response

```json
{
  "success": true,
  "data": {
    "project_id": 1,
    "indexed_files": 24,
    "indexed_chunks": 132,
    "skipped_files": 5,
    "deleted_files": 2,
    "status": "COMPLETED"
  },
  "request_id": "req_abc123"
}
```

#### Errors

| Code | Status | Description |
|---|---:|---|
| PROJECT_NOT_FOUND | 404 | 프로젝트를 찾을 수 없음 |
| INDEXING_FAILED | 500 | 코드 인덱싱 중 오류 발생 |
| EMBEDDING_FAILED | 502 | Embedding API 호출 실패 |

---

### POST /api/index/docs

공식문서 또는 내부문서를 인덱싱합니다.

`path`(로컬 Markdown 파일) 또는 `url`(웹페이지) 중 하나를 전달합니다. 둘 다 전달하거나 둘 다 비어있으면 `INVALID_REQUEST`를 반환합니다.

#### Request (로컬 파일)

```json
{
  "doc_name": "fastapi-response-docs",
  "source_type": "official_doc",
  "path": "./data/official_docs/fastapi_response.md"
}
```

#### Request (URL)

```json
{
  "doc_name": "fastapi-response-docs",
  "source_type": "official_doc",
  "url": "https://fastapi.tiangolo.com/tutorial/response-model/",
  "max_depth": 2
}
```

`max_depth`는 선택값이며 기본값 2, 최대 3까지 허용합니다. 1이면 해당 페이지만, 2 이상이면 시작 URL의 최상위 경로 segment(예: `/ko/`) 하위의 링크를 따라 하위 페이지까지 함께 수집합니다 (`prevent_outside=true`로 도메인 밖 이동 차단 + 최상위 경로 segment로 제한해 다국어 문서 사이트 등에서 `/en/`, `/de/` 같은 다른 섹션까지 새는 것을 방지, css/js/이미지 등 정적 자산은 제외). 한 번의 요청에서 최대 150페이지까지만 수집합니다.

#### Response

```json
{
  "success": true,
  "data": {
    "doc_name": "fastapi-response-docs",
    "indexed_documents": 3,
    "indexed_chunks": 42,
    "skipped_documents": 0,
    "status": "COMPLETED",
    "page_tree": "fastapi.tiangolo.com\n└── tutorial/\n    └── response-model/\n        ├── extra-models/\n        └── response-multiple-models/"
  },
  "request_id": "req_abc123"
}
```

URL 크롤링으로 여러 페이지가 수집된 경우 `indexed_documents`는 페이지 수를 나타내고, `page_tree`에 수집된 페이지 경로를 트리 형태 문자열로 표시합니다. 로컬 파일(`path`) 인덱싱이거나 단일 페이지(`max_depth=1`)인 경우 `page_tree`는 `null`입니다.

#### Errors

| Code | Status | Description |
|---|---:|---|
| DOCUMENT_PATH_NOT_FOUND | 400 | 문서 경로가 존재하지 않음 |
| UNSUPPORTED_FILE_TYPE | 400 | 지원하지 않는 문서 형식 |
| DOCUMENT_FETCH_FAILED | 502 | URL에서 문서를 가져오는 데 실패함 |
| INDEXING_FAILED | 500 | 문서 인덱싱 실패 |
| EMBEDDING_FAILED | 502 | Embedding API 호출 실패 |

---

## 7. Review API

### POST /api/reviews

사용자 질문을 기반으로 코드와 공식문서를 검색하고 리뷰 결과를 생성합니다.

#### Request

```json
{
  "project_id": 1,
  "question": "이 JSONResponse 사용 방식 공식문서 기준으로 괜찮아?",
  "code_top_k": 5,
  "doc_top_k": 5
}
```

#### Response

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
    "model": "mistral-small-latest",
    "latency_ms": 2840
  },
  "request_id": "req_abc123"
}
```

#### Errors

| Code | Status | Description |
|---|---:|---|
| PROJECT_NOT_FOUND | 404 | 프로젝트를 찾을 수 없음 |
| EMPTY_QUESTION | 400 | 질문이 비어 있음 |
| RETRIEVAL_FAILED | 500 | 검색 실패 |
| LLM_CALL_FAILED | 502 | LLM API 호출 실패 |

---

### GET /api/reviews/{review_id}

리뷰 결과를 조회합니다.

#### Response

```json
{
  "success": true,
  "data": {
    "review_id": 10,
    "project_id": 1,
    "question": "이 JSONResponse 사용 방식 공식문서 기준으로 괜찮아?",
    "answer": "현재 코드는 ...",
    "created_at": "2026-07-01T12:10:00"
  },
  "request_id": "req_abc123"
}
```

#### Errors

| Code | Status | Description |
|---|---:|---|
| REVIEW_NOT_FOUND | 404 | 리뷰 결과를 찾을 수 없음 |

---

### GET /api/projects/{project_id}/reviews

프로젝트의 리뷰 히스토리 목록을 최신순으로 조회합니다 (UI의 히스토리 화면용, #32).

#### Response

```json
{
  "success": true,
  "data": [
    {
      "review_id": 10,
      "question": "이 JSONResponse 사용 방식 공식문서 기준으로 괜찮아?",
      "verdict": "PROBLEM",
      "created_at": "2026-07-01T12:10:00"
    }
  ],
  "request_id": "req_abc123"
}
```

---

## 8. Retrieval API

### GET /api/retrievals/{review_id}

특정 리뷰 요청에서 검색된 chunk 목록을 조회합니다.

#### Response

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
      },
      {
        "rank": 2,
        "source_type": "official_doc",
        "source": "fastapi_response.md",
        "score": 0.79,
        "preview": "Use jsonable_encoder in a Response..."
      }
    ]
  },
  "request_id": "req_abc123"
}
```

#### Errors

| Code | Status | Description |
|---|---:|---|
| REVIEW_NOT_FOUND | 404 | 리뷰 결과를 찾을 수 없음 |

---

## 9. Log API

초기 버전에서는 로그 조회 API는 선택 기능입니다. 로그는 우선 콘솔 또는 파일에 구조화된 JSON 형태로 출력합니다.

향후 다음 API를 추가할 수 있습니다.

```text
GET /api/logs/requests
GET /api/logs/errors
GET /api/logs/rag-executions
```

---

## 10. API 설계 원칙

1. 모든 응답에는 `request_id`를 포함합니다.
2. 모든 실패 응답은 공통 에러 형식을 따릅니다.
3. 인덱싱 API는 처리 결과 요약을 반환합니다.
4. 리뷰 API는 답변뿐 아니라 검색 근거도 함께 반환합니다.
5. API 문서는 FastAPI Swagger UI에서 확인 가능해야 합니다.
