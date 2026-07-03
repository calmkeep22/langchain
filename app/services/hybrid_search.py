import json

from sqlalchemy.orm import Session

from app.core.fts import get_fts_content, search_fts
from app.core.vector_store import get_code_vector_store, get_docs_vector_store
from app.models.chunk import Chunk

RRF_K = 60
DENSE_K = 20
SPARSE_K = 20


def reciprocal_rank_fusion(rank_lists: list[list[int]], k: int = RRF_K) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranked_ids in rank_lists:
        for rank, chunk_id in enumerate(ranked_ids, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1 / (k + rank)
    return scores


def _resolve_chunk_id(db: Session, vector_id: str | None) -> int | None:
    if not vector_id:
        return None
    chunk = db.query(Chunk).filter(Chunk.vector_id == vector_id).first()
    return chunk.id if chunk else None


def _hybrid_search(
    db: Session,
    vector_store,
    question: str,
    top_k: int,
    *,
    project_id: int | None = None,
    source_type: str | None = None,
    rrf_k: int = RRF_K,
) -> list[dict]:
    dense_filter = {"project_id": project_id} if project_id is not None else None
    dense_results = vector_store.similarity_search_with_score(
        question, k=DENSE_K, filter=dense_filter
    )

    dense_items: dict[int, dict] = {}
    dense_rank_ids: list[int] = []
    for doc, _score in dense_results:
        chunk_id = _resolve_chunk_id(db, doc.metadata.get("vector_id"))
        if chunk_id is None:
            continue
        dense_rank_ids.append(chunk_id)
        dense_items[chunk_id] = {
            "chunk_id": chunk_id,
            "metadata": doc.metadata,
            "text": doc.page_content,
        }

    sparse_results = search_fts(
        db, question, project_id=project_id, source_type=source_type, limit=SPARSE_K
    )
    sparse_rank_ids = [chunk_id for chunk_id, _score in sparse_results]

    sparse_items: dict[int, dict] = {}
    for chunk_id in sparse_rank_ids:
        if chunk_id in dense_items:
            continue
        chunk = db.query(Chunk).filter(Chunk.id == chunk_id).first()
        if not chunk:
            continue
        metadata = json.loads(chunk.metadata_json) if chunk.metadata_json else {}
        text = get_fts_content(db, chunk_id) or chunk.content_preview or ""
        sparse_items[chunk_id] = {"chunk_id": chunk_id, "metadata": metadata, "text": text}

    combined = {**sparse_items, **dense_items}
    if not combined:
        return []

    rrf_scores = reciprocal_rank_fusion([dense_rank_ids, sparse_rank_ids], k=rrf_k)
    ranked_ids = sorted(combined.keys(), key=lambda cid: rrf_scores.get(cid, 0.0), reverse=True)

    return [
        {**combined[chunk_id], "score": round(rrf_scores.get(chunk_id, 0.0), 5)}
        for chunk_id in ranked_ids[:top_k]
    ]


def hybrid_search_code(
    db: Session, embeddings, question: str, project_id: int, top_k: int = 5, rrf_k: int = RRF_K
) -> list[dict]:
    vector_store = get_code_vector_store(embeddings)
    return _hybrid_search(
        db, vector_store, question, top_k, project_id=project_id, source_type="code", rrf_k=rrf_k
    )


def hybrid_search_docs(
    db: Session, embeddings, question: str, top_k: int = 5, rrf_k: int = RRF_K
) -> list[dict]:
    vector_store = get_docs_vector_store(embeddings)
    return _hybrid_search(db, vector_store, question, top_k, source_type="official_doc", rrf_k=rrf_k)
