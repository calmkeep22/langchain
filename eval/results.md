# Retrieval Evaluation Log

`eval/dataset.json` 기준, `eval/run_eval.py`로 측정한 결과 기록.

측정 대상: 이 저장소의 `app/` 폴더 (35개 질문, 파일 단위 정답 매칭)

| Version | 청킹 | 검색 | 후처리 | Hit@1 | Hit@3 | Recall@5 | MRR |
|---|---|---|---|---|---|---|---|
| V1 | RecursiveCharacterTextSplitter (1200/200) | Dense (Mistral) | 없음 | 0.829 (29/35) | 0.943 (33/35) | 0.943 (33/35) | 0.886 |

## 실행 방법

```bash
python eval/run_eval.py --label V1
```

`.env`에 `MISTRAL_API_KEY` 또는 `OPENAI_API_KEY`가 설정되어 있어야 한다.

## V1 관찰 사항

35개 중 2개 MISS, 둘 다 짧고 심볼 정보가 없는 파일이 대상일 때 발생했다.

- ".venv, __pycache__ 제외 디렉토리" 질문 → `code_loader.py` 대신 `code_indexing_service.py`가 1위로 검색됨
- "서버 시작 시 SQLite 테이블 생성" 질문 → `main.py` 대신 테이블 정의가 있는 model 파일들이 상위로 검색됨

두 경우 모두 파일 하나가 통째로 하나의 chunk가 되면서, 그 안에서 어떤 부분이 질문과 관련 있는지 구분이 안 되는 게 원인으로 보인다. AST 기반 심볼 단위 청킹(#13)이 이 문제를 직접 해결할 가능성이 높다.

## 다음 비교 대상

- V2: AST 기반 Python 청킹 + fallback (#13)
- V3: Dense + BM25 하이브리드 검색 (#14)
- V4: V3 + Reranking (#15)
- V5: V4 + Parent 컨텍스트 확장 (#13, Small-to-Big)
