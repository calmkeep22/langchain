# 06. Logging Policy

## 1. 문서 목적

이 문서는 RAG Code Reviewer의 로깅 정책을 정의합니다.

이 프로젝트에서 로깅은 단순 디버깅 목적이 아니라 다음 목적을 가집니다.

- API 요청 추적
- RAG 실행 과정 추적
- 검색 품질 분석
- LLM 호출 실패 분석
- 인덱싱 실패 원인 분석
- 에러 대응 및 트러블슈팅

---

## 2. 로깅 목표

### 2.1 추적성

모든 요청은 `request_id`로 추적 가능해야 합니다.

하나의 요청에서 발생하는 다음 이벤트는 동일한 request_id를 공유합니다.

- HTTP request log
- service log
- retrieval log
- LLM call log
- error log

---

### 2.2 구조화

로그는 가능한 JSON 형태로 출력합니다.

문자열 로그 예시:

```text
Review completed
```

위 방식은 분석이 어렵습니다.

구조화 로그 예시:

```json
{
  "level": "INFO",
  "event": "rag_review_completed",
  "request_id": "req_abc123",
  "review_id": 10,
  "latency_ms": 2840
}
```

---

### 2.3 민감정보 보호

로그에 다음 값은 기록하지 않습니다.

- LLM API Key
- Authorization header
- 비밀번호
- 개인정보
- 전체 `.env` 내용
- 지나치게 긴 원본 코드 전문

질문과 답변은 개발 환경에서는 기록할 수 있지만, 운영 환경에서는 마스킹 또는 저장 정책을 별도로 둡니다.

---

## 3. Request ID 정책

### 3.1 생성 방식

클라이언트가 `X-Request-ID`를 전달하면 해당 값을 사용합니다.

전달하지 않으면 서버가 UUID 기반 request_id를 생성합니다.

### 3.2 포함 위치

request_id는 다음 위치에 포함됩니다.

- 응답 body
- request log
- error log
- RAG execution log
- retrieval log

응답 예시:

```json
{
  "success": true,
  "data": {},
  "request_id": "req_abc123"
}
```

---

## 4. 로그 레벨 정책

| Level | 사용 기준 |
|---|---|
| DEBUG | 개발 환경 상세 디버깅 정보 |
| INFO | 정상 요청, 인덱싱 완료, RAG 완료 |
| WARNING | 검색 결과 부족, fallback 발생, 비정상 가능성 |
| ERROR | 요청 처리 실패, LLM API 실패, 인덱싱 실패 |
| CRITICAL | 서비스 지속 불가능 수준의 장애 |

---

## 5. HTTP 요청 로그

### 5.1 요청 시작 로그

이벤트명:

```text
http_request_started
```

필드:

| Field | Description |
|---|---|
| event | 이벤트 이름 |
| request_id | 요청 추적 ID |
| method | HTTP method |
| path | 요청 path |
| client_ip | 클라이언트 IP |
| user_agent | User-Agent |
| timestamp | 요청 시작 시간 |

예시:

```json
{
  "level": "INFO",
  "event": "http_request_started",
  "request_id": "req_abc123",
  "method": "POST",
  "path": "/api/reviews",
  "client_ip": "127.0.0.1",
  "user_agent": "curl/8.0",
  "timestamp": "2026-07-01T12:00:00"
}
```

---

### 5.2 요청 완료 로그

이벤트명:

```text
http_request_completed
```

필드:

| Field | Description |
|---|---|
| event | 이벤트 이름 |
| request_id | 요청 추적 ID |
| method | HTTP method |
| path | 요청 path |
| status_code | HTTP status code |
| latency_ms | 처리 시간 |
| timestamp | 완료 시간 |

예시:

```json
{
  "level": "INFO",
  "event": "http_request_completed",
  "request_id": "req_abc123",
  "method": "POST",
  "path": "/api/reviews",
  "status_code": 200,
  "latency_ms": 2950,
  "timestamp": "2026-07-01T12:00:03"
}
```

---

## 6. 인덱싱 로그

### 6.1 코드 인덱싱 완료 로그

이벤트명:

```text
code_indexing_completed
```

예시:

```json
{
  "level": "INFO",
  "event": "code_indexing_completed",
  "request_id": "req_abc123",
  "project_id": 1,
  "indexed_files": 24,
  "indexed_chunks": 132,
  "skipped_files": 5,
  "latency_ms": 4180,
  "timestamp": "2026-07-01T12:05:00"
}
```

---

### 6.2 공식문서 인덱싱 완료 로그

이벤트명:

```text
docs_indexing_completed
```

예시:

```json
{
  "level": "INFO",
  "event": "docs_indexing_completed",
  "request_id": "req_abc123",
  "document_id": 3,
  "doc_name": "fastapi-response-docs",
  "indexed_chunks": 18,
  "latency_ms": 1200,
  "timestamp": "2026-07-01T12:06:00"
}
```

---

## 7. RAG 실행 로그

### 7.1 RAG 시작 로그

이벤트명:

```text
rag_review_started
```

예시:

```json
{
  "level": "INFO",
  "event": "rag_review_started",
  "request_id": "req_abc123",
  "project_id": 1,
  "question_length": 37,
  "code_top_k": 5,
  "doc_top_k": 5,
  "timestamp": "2026-07-01T12:10:00"
}
```

---

### 7.2 Retrieval 로그

이벤트명:

```text
retrieval_completed
```

예시:

```json
{
  "level": "INFO",
  "event": "retrieval_completed",
  "request_id": "req_abc123",
  "project_id": 1,
  "code_chunks": 5,
  "doc_chunks": 3,
  "top_code_score": 0.82,
  "top_doc_score": 0.79,
  "latency_ms": 310,
  "timestamp": "2026-07-01T12:10:01"
}
```

---

### 7.3 LLM 호출 로그

이벤트명:

```text
llm_call_completed
```

예시:

```json
{
  "level": "INFO",
  "event": "llm_call_completed",
  "request_id": "req_abc123",
  "model": "mistral-small-latest",
  "input_tokens": 3200,
  "output_tokens": 650,
  "latency_ms": 2210,
  "timestamp": "2026-07-01T12:10:03"
}
```

토큰 정보를 제공하지 않는 LLM API를 사용할 경우 해당 필드는 null로 둘 수 있습니다.

---

### 7.4 RAG 완료 로그

이벤트명:

```text
rag_review_completed
```

예시:

```json
{
  "level": "INFO",
  "event": "rag_review_completed",
  "request_id": "req_abc123",
  "review_id": 10,
  "project_id": 1,
  "verdict": "PROBLEM",
  "code_chunks": 5,
  "doc_chunks": 3,
  "model": "mistral-small-latest",
  "latency_ms": 2840,
  "timestamp": "2026-07-01T12:10:03"
}
```

---

## 8. 에러 로그

이벤트명:

```text
error_occurred
```

필드:

| Field | Description |
|---|---|
| event | 이벤트 이름 |
| request_id | 요청 추적 ID |
| error_code | 서비스 에러 코드 |
| message | 에러 메시지 |
| path | 요청 path |
| status_code | HTTP status code |
| stack_trace | stack trace, 개발 환경에서만 사용 |

예시:

```json
{
  "level": "ERROR",
  "event": "error_occurred",
  "request_id": "req_abc123",
  "error_code": "LLM_CALL_FAILED",
  "message": "LLM API request failed.",
  "path": "/api/reviews",
  "status_code": 502,
  "stack_trace": "...",
  "timestamp": "2026-07-01T12:10:03"
}
```

---

## 9. 검색 품질 분석 로그

검색 품질 개선을 위해 다음 값을 저장하거나 로그로 남깁니다.

| Field | Description |
|---|---|
| review_id | 리뷰 ID |
| query | 원본 질문 또는 재작성 쿼리 |
| source_type | code 또는 official_doc |
| chunk_id | 검색된 chunk ID |
| rank | 검색 순위 |
| score | 유사도 점수 |
| source | 파일 경로 또는 문서 출처 |

이 정보는 RAG 품질 개선에 사용됩니다.

---

## 10. 로그 저장 방식

초기 버전:

- 콘솔 출력
- 필요 시 `logs/app.log` 파일 저장
- request_logs, error_logs는 SQLite 저장 가능

향후 확장:

- OpenTelemetry tracing
- Grafana/Loki
- ELK stack
- LangSmith trace

---

## 11. 로깅 구현 원칙

1. 비즈니스 로직에서 `print()`를 사용하지 않습니다.
2. 모든 주요 이벤트는 event 이름을 명확히 지정합니다.
3. request_id는 middleware에서 생성하고 context로 전달합니다.
4. 에러 발생 시 공통 exception handler에서 error log를 남깁니다.
5. LLM 입력 prompt 전체는 기본적으로 로그에 남기지 않습니다.
6. 검색된 chunk preview는 길이를 제한합니다.
7. 운영 환경에서는 민감정보를 마스킹합니다.
