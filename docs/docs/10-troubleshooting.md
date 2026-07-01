# 10. Troubleshooting

## 1. 문서 목적

이 문서는 RAG Code Reviewer 개발 및 실행 중 발생할 수 있는 문제와 해결 방법을 정리합니다.

초기에는 개발 중 발견한 문제를 계속 추가하는 방식으로 관리합니다.

---

## 2. 서버 실행 문제

### 2.1 uvicorn 실행 시 app.main을 찾지 못하는 경우

#### 증상

```text
Error loading ASGI app. Could not import module "app.main".
```

#### 원인

- 프로젝트 루트가 아닌 위치에서 명령어 실행
- `app/main.py` 파일이 없음
- Python module path 문제

#### 해결

프로젝트 루트에서 실행합니다.

```bash
uvicorn app.main:app --reload
```

프로젝트 구조를 확인합니다.

```text
rag-code-reviewer/
  app/
    main.py
```

---

## 3. 환경변수 문제

### 3.1 LLM API Key가 없다는 에러

#### 증상

```json
{
  "success": false,
  "error": {
    "code": "LLM_API_KEY_MISSING",
    "message": "LLM API key is missing."
  }
}
```

#### 원인

- `.env` 파일이 없음
- API Key 이름이 잘못됨
- `load_dotenv()`가 호출되지 않음

#### 해결

`.env` 파일을 생성합니다.

```env
MISTRAL_API_KEY=your_mistral_api_key
OPENAI_API_KEY=your_openai_api_key
```

서버 시작 시 환경변수를 로드하는지 확인합니다.

---

## 4. 프로젝트 인덱싱 문제

### 4.1 INVALID_PROJECT_PATH 발생

#### 증상

```json
{
  "success": false,
  "error": {
    "code": "INVALID_PROJECT_PATH",
    "message": "Project path is invalid."
  }
}
```

#### 원인

- 입력한 root_path가 존재하지 않음
- 상대 경로 기준이 서버 실행 위치와 다름
- 파일 경로를 입력했지만 디렉토리가 필요함

#### 해결

경로를 확인합니다.

```bash
ls ./data/sample_projects/fastapi_app
```

절대 경로로 다시 시도합니다.

---

### 4.2 인덱싱 결과가 0개인 경우

#### 증상

```json
{
  "indexed_files": 0,
  "indexed_chunks": 0
}
```

#### 원인

- 지원 확장자 파일이 없음
- 제외 디렉토리 안에 파일이 있음
- file loader 필터 조건이 너무 강함

#### 해결

지원 확장자를 확인합니다.

```text
.py, .md, .yml, .yaml, .json
```

file loader 로그를 DEBUG로 확인합니다.

---

## 5. 공식문서 인덱싱 문제

### 5.1 DOCUMENT_PATH_NOT_FOUND 발생

#### 원인

- Markdown 문서 경로가 잘못됨
- 서버 실행 위치 기준 상대 경로가 다름

#### 해결

```bash
ls ./data/official_docs/fastapi_response.md
```

---

### 5.2 UNSUPPORTED_FILE_TYPE 발생

#### 원인

초기 버전은 Markdown 파일만 공식문서로 지원합니다.

#### 해결

문서를 `.md` 형식으로 저장합니다.

---

## 6. Vector Store 문제

### 6.1 검색 결과가 비어 있는 경우

#### 증상

리뷰 API 응답에서 related_code 또는 official_references가 비어 있음.

#### 원인

- 인덱싱이 수행되지 않음
- Chroma persist_directory가 다름
- collection_name이 다름
- 질문이 너무 모호함

#### 해결

1. 코드 인덱싱 API를 먼저 호출합니다.
2. 공식문서 인덱싱 API를 먼저 호출합니다.
3. Chroma 경로 설정을 확인합니다.
4. 질문을 더 구체적으로 작성합니다.

예:

```text
나쁨: 이거 괜찮아?
좋음: FastAPI JSONResponse에 Pydantic 모델을 직접 넣는 코드 괜찮아?
```

---

### 6.2 기존 인덱스가 계속 남아 있는 경우

#### 원인

Chroma persist directory에 이전 데이터가 남아 있음.

#### 해결

개발 환경에서는 Chroma 디렉토리를 삭제 후 재인덱싱할 수 있습니다.

```bash
rm -rf ./data/chroma
```

주의: 운영 데이터에는 사용하지 않습니다.

---

## 7. LLM 호출 문제

### 7.1 LLM_CALL_FAILED 발생

#### 원인

- API Key 오류
- provider 장애
- 네트워크 오류
- 요청량 제한 초과

#### 해결

- `.env` API Key 확인
- provider billing/usage 확인
- 네트워크 확인
- 로그에서 request_id 기준으로 상세 오류 확인

---

### 7.2 LLM_TIMEOUT 발생

#### 원인

- LLM 응답 지연
- context가 너무 큼
- 네트워크 지연

#### 해결

- top_k를 줄입니다.
- chunk_size를 줄입니다.
- timeout 설정을 늘립니다.
- prompt에 포함되는 context 길이를 제한합니다.

---

## 8. 답변 품질 문제

### 8.1 답변이 너무 일반적인 경우

#### 원인

- 관련 코드 chunk가 검색되지 않음
- 공식문서 chunk가 검색되지 않음
- prompt에서 근거 기반 답변을 강제하지 않음

#### 해결

- retrieval 결과를 확인합니다.
- 질문을 구체화합니다.
- prompt에 다음 지시를 추가합니다.

```text
반드시 제공된 코드와 공식문서에 근거해서 답변해라.
근거가 부족하면 추측하지 말고 "근거 부족"이라고 말해라.
```

---

### 8.2 존재하지 않는 파일이나 함수명을 언급하는 경우

#### 원인

LLM hallucination 가능성이 있습니다.

#### 해결

- 답변에 사용할 수 있는 파일명을 retrieved context로 제한합니다.
- prompt에 context 외 파일 언급 금지 조건을 추가합니다.
- related_code를 별도 구조로 반환하고 사용자에게 확인 가능하게 합니다.

---

## 9. 로깅 문제

### 9.1 request_id가 응답에 없는 경우

#### 원인

- request_id middleware가 적용되지 않음
- response wrapper에서 request_id를 누락함

#### 해결

- middleware 등록 순서 확인
- request.state.request_id 설정 여부 확인
- 공통 응답 생성 함수에서 request_id 포함 여부 확인

---

### 9.2 로그가 너무 길어지는 경우

#### 원인

- prompt 전문 또는 코드 전문을 로그에 기록함

#### 해결

- prompt 전체 대신 prompt_length만 기록합니다.
- chunk content는 preview만 기록합니다.
- 민감정보 마스킹 정책을 적용합니다.

---

## 10. 개발 중 권장 확인 순서

문제가 발생하면 다음 순서로 확인합니다.

```text
1. request_id 확인
2. HTTP request log 확인
3. error log 확인
4. indexing log 확인
5. retrieval log 확인
6. LLM call log 확인
7. SQLite metadata 확인
8. Chroma collection 확인
```

---

## 11. 향후 추가할 항목

개발 중 다음 문제가 발생하면 이 문서에 추가합니다.

- SQLite migration 문제
- Chroma collection 충돌 문제
- embedding model 변경 문제
- query rewriting 실패 사례
- chunking 품질 문제
- 공식문서 최신화 문제
