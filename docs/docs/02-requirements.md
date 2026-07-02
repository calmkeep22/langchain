# 02. Requirements

## 1. 문서 목적

이 문서는 RAG Code Reviewer의 기능 요구사항, 비기능 요구사항, 제외 범위를 정의합니다.

초기 버전은 로컬 환경에서 FastAPI 기반 API 서버로 동작하는 MVP를 기준으로 합니다.

---

## 2. 기능 요구사항

### FR-001. 코드 프로젝트 등록

사용자는 분석 대상 코드 프로젝트를 등록할 수 있어야 합니다.

- 입력값: 프로젝트 이름, 로컬 루트 경로
- 시스템은 경로가 존재하는지 확인해야 합니다.
- 동일한 프로젝트 이름이 이미 존재하는 경우 정책에 따라 거부하거나 갱신해야 합니다.

---

### FR-002. 코드 인덱싱

시스템은 등록된 프로젝트의 코드 파일을 읽고 벡터 DB에 인덱싱할 수 있어야 합니다.

- 초기 지원 확장자: `.py`, `.md`, `.yml`, `.yaml`, `.json`, `.env.example`
- 제외 디렉토리: `.git`, `.venv`, `venv`, `__pycache__`, `node_modules`, `dist`, `build`, `target`
- 초기 chunk 단위: 파일 단위 또는 단순 text chunk
- 향후 확장: 함수/클래스/메서드 단위 chunking

---

### FR-003. 공식문서 등록

사용자는 공식문서 또는 내부문서를 등록할 수 있어야 합니다.

- 초기 입력 형식: Markdown 파일 또는 URL
- URL 입력 시 같은 도메인 내에서 링크를 따라 하위 페이지까지 함께 수집할 수 있어야 합니다 (max_depth로 범위 제한, 도메인 밖으로는 이동하지 않음)
- 문서 유형: official_doc, internal_doc, error_doc
- 문서 출처와 제목을 metadata로 저장해야 합니다.

---

### FR-004. 공식문서 인덱싱

시스템은 Markdown 문서(또는 URL에서 가져온 문서)를 구조 기반으로 분할하고 벡터 DB에 저장할 수 있어야 합니다.

- URL로 가져온 HTML은 헤더 구조(`<h1>~<h3>`)를 Markdown 헤더 문법으로 변환한 뒤 동일한 분할 전략을 적용합니다.
- Markdown header 기반 분할을 우선 적용합니다.
- 긴 section은 추가 text splitter로 재분할할 수 있습니다.
- 각 chunk에는 source, title, section, chunk_index를 metadata로 저장해야 합니다.
- URL 크롤링으로 여러 페이지를 수집한 경우, 수집된 페이지 목록을 트리 구조로 로그와 응답에 남겨야 합니다.

---

### FR-005. 리뷰 질문 요청

사용자는 특정 프로젝트에 대해 코드 설명 또는 코드 리뷰 질문을 요청할 수 있어야 합니다.

- 입력값: project_id, question
- 시스템은 question을 기반으로 관련 코드 chunk와 공식문서 chunk를 검색해야 합니다.
- 검색 결과를 LLM prompt에 주입하여 답변을 생성해야 합니다.

---

### FR-006. 코드 검색

시스템은 사용자 질문과 관련된 코드 chunk를 검색해야 합니다.

- 기본 검색 방식: vector similarity search
- 기본 검색 개수: top_k=5
- 검색 결과에는 file_path, start_line, end_line, symbol_name metadata가 포함될 수 있어야 합니다.

---

### FR-007. 공식문서 검색

시스템은 사용자 질문과 관련된 공식문서 chunk를 검색해야 합니다.

- 기본 검색 방식: vector similarity search
- 기본 검색 개수: top_k=5
- 검색 결과에는 source, title, section metadata가 포함되어야 합니다.

---

### FR-008. RAG 기반 답변 생성

시스템은 검색된 코드와 공식문서를 기반으로 답변을 생성해야 합니다.

답변에는 다음 항목이 포함되어야 합니다.

- 결론
- 관련 코드 위치
- 공식문서 근거
- 문제 설명
- 수정 방향
- 필요 시 수정 예시 코드

---

### FR-009. 검색 근거 반환

시스템은 LLM 답변과 함께 검색된 코드 및 문서 근거를 반환해야 합니다.

- related_code
- official_references
- retrieval score
- chunk rank

---

### FR-010. 리뷰 결과 저장

시스템은 질문과 답변 결과를 저장해야 합니다.

저장 항목:

- question
- answer
- project_id
- latency_ms
- model_name
- created_at

---

### FR-011. 검색 로그 저장

시스템은 각 리뷰 요청에 대해 검색된 chunk 정보를 저장해야 합니다.

저장 항목:

- review_id
- chunk_id
- rank
- score
- source_type

---

### FR-012. request_id 기반 요청 추적

시스템은 모든 API 요청에 request_id를 부여해야 합니다.

- request_id는 로그와 응답에 포함되어야 합니다.
- 클라이언트가 `X-Request-ID`를 전달하면 해당 값을 사용할 수 있습니다.
- 전달하지 않으면 서버가 UUID 기반으로 생성합니다.

---

### FR-013. 구조화 로깅

시스템은 주요 이벤트를 구조화된 JSON 형태로 기록해야 합니다.

주요 이벤트:

- http_request_started
- http_request_completed
- code_indexing_completed
- docs_indexing_completed
- rag_review_started
- rag_review_completed
- error_occurred

---

### FR-014. 표준 에러 응답

시스템은 모든 예외에 대해 동일한 에러 응답 구조를 제공해야 합니다.

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

## 3. 비기능 요구사항

### NFR-001. 로컬 실행 가능성

초기 버전은 로컬 환경에서 실행 가능해야 합니다.

- 외부 서버 없이 실행 가능해야 합니다.
- LLM API와 embedding API는 외부 API를 사용할 수 있습니다.

---

### NFR-002. API Key 보안

LLM API Key는 코드에 직접 작성하지 않고 환경변수로 관리해야 합니다.

- `.env` 사용
- `.env`는 Git에 포함하지 않음
- `.env.example` 제공

---

### NFR-003. 추적성

모든 요청은 request_id로 추적 가능해야 합니다.

- 응답에 request_id 포함
- 요청 로그에 request_id 포함
- 에러 로그에 request_id 포함
- RAG 실행 로그에 request_id 포함

---

### NFR-004. 문서화

주요 API와 설계 문서는 문서화되어야 합니다.

- FastAPI Swagger UI 제공
- Markdown 기반 설계 문서 제공
- 에러 코드 문서 제공
- 로깅 정책 문서 제공

---

### NFR-005. 확장성

초기 구조는 다음 확장을 고려해야 합니다.

- GitHub Repository URL 기반 인덱싱
- 함수/클래스 단위 코드 파싱
- 다중 프로젝트 관리
- query rewriting
- reranking
- Docker 배포

---

### NFR-006. 실패 처리

외부 LLM API 호출 실패, vector DB 검색 실패, 인덱싱 실패에 대해 명확한 에러 코드를 반환해야 합니다.

---

## 4. 제외 범위

초기 MVP에서는 다음 기능을 구현하지 않습니다.

- 사용자 회원가입/로그인
- 프론트엔드 UI
- GitHub OAuth
- PR 자동 리뷰
- 클라우드 배포
- 실시간 채팅 UI
- 대규모 조직 단위 권한 관리
- 비용 관리 대시보드

---

## 5. 우선순위

| 우선순위 | 요구사항 |
|---|---|
| P0 | 코드 인덱싱, 공식문서 인덱싱, 리뷰 질문, RAG 답변, request_id 로깅 |
| P1 | 검색 근거 저장, 에러 코드 문서화, Swagger 문서 정리 |
| P2 | query rewriting, 함수/클래스 chunking, retrieval score 개선 |
| P3 | GitHub 연동, 프론트엔드 UI, 배포 자동화 |
