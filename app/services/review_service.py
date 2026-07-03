import time
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.embeddings import EmbeddingConfigError, get_embeddings
from app.core.errors import ServiceError
from app.core.llm import LLMConfigError, get_llm
from app.core.logging import log_event
from app.core.vector_store import get_code_vector_store, get_docs_vector_store
from app.models.chunk import Chunk
from app.models.retrieval_log import RetrievalLog
from app.models.review import Review
from app.services.project_service import get_project

PROMPT_TEMPLATE = """너는 백엔드 코드 리뷰어다.
반드시 제공된 코드와 공식문서에 근거해서 답변해라.
근거가 부족하면 추측하지 말고 "근거 부족"이라고 말해라.

[사용자 질문]
{question}

[관련 코드]
{code_context}

[관련 공식문서]
{doc_context}

[답변 형식]
1. 결론
2. 관련 코드 위치
3. 공식문서 근거
4. 문제 설명
5. 수정 방향
6. 수정 예시
"""


class Verdict(str, Enum):
    OK = "OK"
    PROBLEM = "PROBLEM"
    NEEDS_IMPROVEMENT = "NEEDS_IMPROVEMENT"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"


class ReviewAnswer(BaseModel):
    verdict: Verdict = Field(description="이 질문/코드에 대한 종합 판단")
    answer: str = Field(
        description="결론, 관련 코드 위치, 공식문서 근거, 문제 설명, 수정 방향, 수정 예시를 포함한 한국어 답변 전문"
    )


def _read_line_range(root_path: str, relative_path: str, start_line: int, end_line: int) -> str | None:
    try:
        lines = (Path(root_path) / relative_path).read_text(encoding="utf-8", errors="ignore").splitlines()
        return "\n".join(lines[start_line - 1 : end_line])
    except OSError:
        return None


def _build_code_context(results: list[tuple], project_root_path: str) -> tuple[str, list[dict]]:
    if not results:
        return "(검색된 코드 없음)", []

    blocks = []
    related_code = []
    for doc, score in results:
        meta = doc.metadata
        file_path = meta.get("file_path")
        start_line = meta.get("start_line")
        end_line = meta.get("end_line")
        parent_start = meta.get("parent_start_line")
        parent_end = meta.get("parent_end_line")

        # Small-to-Big: the match is a small unit (a method), but the LLM gets
        # the whole enclosing class for context, re-read live from disk since
        # only the small chunk's text is stored in the vector store.
        display_start, display_end, code_text = start_line, end_line, doc.page_content
        if parent_start and parent_end:
            expanded = _read_line_range(project_root_path, file_path, parent_start, parent_end)
            if expanded is not None:
                display_start, display_end, code_text = parent_start, parent_end, expanded

        blocks.append(f"File: {file_path} (L{display_start}-{display_end})\n{code_text}")
        related_code.append(
            {
                "file_path": file_path,
                "symbol_name": meta.get("symbol_name"),
                "start_line": start_line,
                "end_line": end_line,
                "score": round(score, 4),
            }
        )
    return "\n\n---\n\n".join(blocks), related_code


def _build_doc_context(results: list[tuple]) -> tuple[str, list[dict]]:
    if not results:
        return "(검색된 공식문서 없음)", []

    blocks = []
    official_references = []
    for doc, score in results:
        meta = doc.metadata
        headers = [h for h in (meta.get("h1"), meta.get("h2"), meta.get("h3")) if h]
        section = " > ".join(headers)
        title = headers[-1] if headers else meta.get("doc_name")
        blocks.append(f"Document: {meta.get('doc_name')}\nSection: {section}\n\n{doc.page_content}")
        official_references.append(
            {
                "title": title,
                "source": meta.get("source"),
                "section": section,
                "score": round(score, 4),
            }
        )
    return "\n\n---\n\n".join(blocks), official_references


def _save_retrieval_logs(
    db: Session, review_id: int, results: list[tuple], source_type: str
) -> None:
    for rank, (doc, score) in enumerate(results, start=1):
        meta = doc.metadata
        vector_id = meta.get("vector_id")
        chunk = db.query(Chunk).filter(Chunk.vector_id == vector_id).first() if vector_id else None
        source = meta.get("file_path") if source_type == "code" else meta.get("source")
        db.add(
            RetrievalLog(
                review_id=review_id,
                chunk_id=chunk.id if chunk else None,
                source_type=source_type,
                source=source,
                rank=rank,
                score=round(score, 4),
            )
        )


def create_review(
    db: Session,
    project_id: int,
    question: str,
    code_top_k: int = 5,
    doc_top_k: int = 5,
    embeddings=None,
    llm=None,
) -> dict:
    if not question or not question.strip():
        raise ServiceError("EMPTY_QUESTION", "Question must not be empty.", 400)

    project = get_project(db, project_id)

    start = time.perf_counter()
    log_event(
        "rag_review_started",
        project_id=project.id,
        question_length=len(question),
        code_top_k=code_top_k,
        doc_top_k=doc_top_k,
    )

    if embeddings is None:
        try:
            embeddings = get_embeddings()
        except EmbeddingConfigError as exc:
            raise ServiceError("EMBEDDING_FAILED", str(exc), 502) from exc

    retrieval_start = time.perf_counter()
    try:
        code_results = get_code_vector_store(embeddings).similarity_search_with_score(
            question, k=code_top_k, filter={"project_id": project.id}
        )
        doc_results = get_docs_vector_store(embeddings).similarity_search_with_score(
            question, k=doc_top_k
        )
    except Exception as exc:
        raise ServiceError("RETRIEVAL_FAILED", "Vector search failed.", 500) from exc

    if not code_results and not doc_results:
        raise ServiceError(
            "NO_RELEVANT_CONTEXT", "No relevant code or documentation found.", 422
        )

    log_event(
        "retrieval_completed",
        project_id=project.id,
        code_chunks=len(code_results),
        doc_chunks=len(doc_results),
        top_code_score=round(code_results[0][1], 4) if code_results else None,
        top_doc_score=round(doc_results[0][1], 4) if doc_results else None,
        latency_ms=int((time.perf_counter() - retrieval_start) * 1000),
    )

    code_context, related_code = _build_code_context(code_results, project.root_path)
    doc_context, official_references = _build_doc_context(doc_results)

    if llm is None:
        try:
            llm = get_llm()
        except LLMConfigError as exc:
            raise ServiceError("LLM_API_KEY_MISSING", str(exc), 500) from exc

    prompt = PROMPT_TEMPLATE.format(
        question=question, code_context=code_context, doc_context=doc_context
    )

    llm_start = time.perf_counter()
    try:
        result: ReviewAnswer = llm.with_structured_output(ReviewAnswer).invoke(prompt)
    except Exception as exc:
        raise ServiceError("LLM_CALL_FAILED", "LLM API request failed.", 502) from exc

    model_name = getattr(llm, "model", None) or getattr(llm, "model_name", None)
    log_event(
        "llm_call_completed",
        model=model_name,
        input_tokens=None,
        output_tokens=None,
        latency_ms=int((time.perf_counter() - llm_start) * 1000),
    )

    latency_ms = int((time.perf_counter() - start) * 1000)

    review = Review(
        project_id=project.id,
        question=question,
        answer=result.answer,
        verdict=result.verdict.value,
        model_name=model_name,
        latency_ms=latency_ms,
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    _save_retrieval_logs(db, review.id, code_results, "code")
    _save_retrieval_logs(db, review.id, doc_results, "official_doc")
    db.commit()

    log_event(
        "rag_review_completed",
        review_id=review.id,
        project_id=project.id,
        verdict=review.verdict,
        code_chunks=len(code_results),
        doc_chunks=len(doc_results),
        model=model_name,
        latency_ms=latency_ms,
    )

    return {
        "review_id": review.id,
        "verdict": review.verdict,
        "answer": review.answer,
        "related_code": related_code,
        "official_references": official_references,
        "model": model_name,
        "latency_ms": latency_ms,
    }


def get_review(db: Session, review_id: int) -> Review:
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise ServiceError("REVIEW_NOT_FOUND", "Review not found.", 404)
    return review
