# 07. Error Code

## 1. 문서 목적

이 문서는 RAG Code Reviewer에서 사용하는 에러 코드와 공통 에러 응답 형식을 정의합니다.

에러 코드를 명확히 관리하면 API 사용자가 문제 원인을 빠르게 이해할 수 있고, 로그 분석과 트러블슈팅이 쉬워집니다.

---

## 2. 공통 에러 응답 형식

모든 에러 응답은 다음 구조를 따릅니다.

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

| Field | Description |
|---|---|
| success | 실패 시 false |
| error.code | 서비스 에러 코드 |
| error.message | 사용자에게 반환할 에러 메시지 |
| request_id | 요청 추적 ID |

---

## 3. 에러 코드 분류

에러 코드는 다음 기준으로 분류합니다.

| Prefix | Category |
|---|---|
| COMMON | 공통 에러 |
| PROJECT | 프로젝트 관련 에러 |
| DOCUMENT | 문서 관련 에러 |
| INDEXING | 인덱싱 관련 에러 |
| RETRIEVAL | 검색 관련 에러 |
| LLM | LLM API 관련 에러 |
| VALIDATION | 요청 검증 에러 |
| SYSTEM | 시스템 내부 에러 |

실제 코드에서는 prefix를 반드시 붙일 필요는 없지만, 문서상 분류를 명확히 합니다.

---

## 4. 공통 에러

| Code | Status | Description |
|---|---:|---|
| INTERNAL_SERVER_ERROR | 500 | 알 수 없는 서버 내부 오류 |
| INVALID_REQUEST | 400 | 요청 형식이 잘못됨 |
| METHOD_NOT_ALLOWED | 405 | 지원하지 않는 HTTP method |
| NOT_FOUND | 404 | 요청한 리소스를 찾을 수 없음 |

---

## 5. 프로젝트 관련 에러

| Code | Status | Description |
|---|---:|---|
| INVALID_PROJECT_PATH | 400 | 프로젝트 경로가 존재하지 않음 |
| PROJECT_ALREADY_EXISTS | 409 | 동일 이름의 프로젝트가 이미 존재함 |
| PROJECT_NOT_FOUND | 404 | 프로젝트를 찾을 수 없음 |
| PROJECT_INDEX_NOT_FOUND | 404 | 프로젝트 인덱스가 존재하지 않음 |

### INVALID_PROJECT_PATH

발생 조건:

- 사용자가 입력한 `root_path`가 존재하지 않는 경우
- 경로가 디렉토리가 아닌 경우

대응 방법:

- 로컬 경로가 올바른지 확인
- 상대 경로 기준이 서버 실행 위치와 일치하는지 확인

---

## 6. 문서 관련 에러

| Code | Status | Description |
|---|---:|---|
| DOCUMENT_PATH_NOT_FOUND | 400 | 문서 경로가 존재하지 않음 |
| DOCUMENT_NOT_FOUND | 404 | 등록된 문서를 찾을 수 없음 |
| UNSUPPORTED_FILE_TYPE | 400 | 지원하지 않는 파일 형식 |
| EMPTY_DOCUMENT | 400 | 문서 내용이 비어 있음 |
| DOCUMENT_FETCH_FAILED | 502 | URL에서 문서를 가져오는 데 실패함 |

### UNSUPPORTED_FILE_TYPE

초기 버전에서 공식문서는 Markdown 파일 또는 URL을 지원합니다.

지원 형식:

```text
.md
http(s):// URL
```

### DOCUMENT_FETCH_FAILED

발생 조건:

- URL 응답이 4xx/5xx인 경우
- 요청 타임아웃
- 네트워크 오류

대응 방법:

- URL이 실제로 접근 가능한지 확인
- 타임아웃/재시도 정책 검토

---

## 7. 인덱싱 관련 에러

| Code | Status | Description |
|---|---:|---|
| INDEXING_FAILED | 500 | 인덱싱 처리 중 오류 발생 |
| CODE_INDEXING_FAILED | 500 | 코드 인덱싱 실패 |
| DOCS_INDEXING_FAILED | 500 | 문서 인덱싱 실패 |
| CHUNKING_FAILED | 500 | chunk 분할 실패 |
| EMBEDDING_FAILED | 502 | embedding API 호출 실패 |
| VECTOR_STORE_WRITE_FAILED | 500 | vector store 저장 실패 |

### EMBEDDING_FAILED

발생 조건:

- API Key 누락
- embedding API timeout
- embedding provider 장애
- 요청 제한 초과

대응 방법:

- `.env`의 API Key 확인
- provider 상태 확인
- 요청량 제한 확인
- 재시도 정책 검토

---

## 8. 검색 관련 에러

| Code | Status | Description |
|---|---:|---|
| RETRIEVAL_FAILED | 500 | vector 검색 실패 |
| CODE_RETRIEVAL_FAILED | 500 | 코드 검색 실패 |
| DOCS_RETRIEVAL_FAILED | 500 | 공식문서 검색 실패 |
| NO_RELEVANT_CONTEXT | 422 | 관련 context를 찾지 못함 |

### NO_RELEVANT_CONTEXT

발생 조건:

- 질문과 관련된 코드나 문서가 검색되지 않은 경우
- 인덱싱이 수행되지 않은 경우
- top_k 검색 결과가 비어 있는 경우

대응 방법:

- 프로젝트 인덱싱 여부 확인
- 공식문서 인덱싱 여부 확인
- 질문을 더 구체적으로 작성
- top_k 증가 검토

---

## 9. LLM 관련 에러

| Code | Status | Description |
|---|---:|---|
| LLM_API_KEY_MISSING | 500 | LLM API Key가 설정되지 않음 |
| LLM_CALL_FAILED | 502 | LLM API 호출 실패 |
| LLM_TIMEOUT | 504 | LLM API 응답 시간 초과 |
| LLM_INVALID_RESPONSE | 502 | LLM 응답 형식이 올바르지 않음 |

### LLM_CALL_FAILED

발생 조건:

- API Key 오류
- provider 장애
- 네트워크 오류
- 요청 제한 초과

대응 방법:

- `.env` 설정 확인
- provider dashboard 확인
- 로그의 request_id로 상세 오류 확인

---

## 10. 요청 검증 에러

| Code | Status | Description |
|---|---:|---|
| EMPTY_QUESTION | 400 | 질문이 비어 있음 |
| QUESTION_TOO_LONG | 400 | 질문 길이가 제한을 초과함 |
| INVALID_TOP_K | 400 | top_k 값이 허용 범위를 벗어남 |
| INVALID_SOURCE_TYPE | 400 | 지원하지 않는 source_type |

---

## 11. 시스템 에러

| Code | Status | Description |
|---|---:|---|
| DATABASE_ERROR | 500 | SQLite 처리 중 오류 발생 |
| VECTOR_STORE_ERROR | 500 | Chroma 처리 중 오류 발생 |
| CONFIGURATION_ERROR | 500 | 서버 설정 오류 |
| FILE_READ_FAILED | 500 | 파일 읽기 실패 |

---

## 12. 에러 처리 원칙

1. 내부 예외를 그대로 사용자에게 노출하지 않습니다.
2. 사용자 응답에는 code와 message만 포함합니다.
3. stack trace는 로그에만 기록합니다.
4. 모든 에러 응답에 request_id를 포함합니다.
5. 외부 API 실패는 502 또는 504로 구분합니다.
6. 사용자의 입력 오류는 400 계열로 처리합니다.
7. 리소스가 없는 경우 404로 처리합니다.

---

## 13. 예외 매핑 예시

| Exception | Error Code | Status |
|---|---|---:|
| ProjectNotFoundException | PROJECT_NOT_FOUND | 404 |
| InvalidProjectPathException | INVALID_PROJECT_PATH | 400 |
| IndexingException | INDEXING_FAILED | 500 |
| RetrievalException | RETRIEVAL_FAILED | 500 |
| LLMCallException | LLM_CALL_FAILED | 502 |
| ValidationException | INVALID_REQUEST | 400 |
