import json

from sqlalchemy.orm import Session

from app.core.fts import get_fts_content, search_fts
from app.core.reranker import rerank
from app.core.vector_store import get_code_vector_store, get_docs_vector_store
from app.models.chunk import Chunk

RRF_K = 60
DENSE_K = 20
SPARSE_K = 20
RERANK_POOL = 20
DEFAULT_MAX_PER_FILE = 2

# use_reranking defaults to False: both FlashRank models tested
# (ms-marco-TinyBERT-L-2-v2, ms-marco-MiniLM-L-12-v2) made results
# substantially worse on this repo's Korean-question / English-code +
# Korean-docstring corpus (MRR 0.86 -> 0.29 / 0.41), not better -- see
# eval/results.md "V4: Reranking (#15)" for the measurements. The
# plumbing is kept so a better-suited reranker can be swapped in later.


def reciprocal_rank_fusion(rank_lists: list[list[int]], k: int = RRF_K) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranked_ids in rank_lists:
        for rank_position, chunk_id in enumerate(ranked_ids, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1 / (k + rank_position)
    return scores


def diversify_by_file(items: list[dict], max_per_file: int | None, limit: int) -> list[dict]:
    """Cap how many chunks from the same file can occupy the candidate pool.

    Without this, a file that strongly matches the query can fill every
    slot with its own chunks, crowding out other genuinely relevant files.
    ``max_per_file=None`` disables the cap (e.g. for a query that's clearly
    about one specific file -- reserved for the future query router, #17).
    """
    if max_per_file is None:
        return items[:limit]

    counts: dict[str, int] = {}
    selected: list[dict] = []
    for item in items:
        meta = item["metadata"]
        key = meta.get("file_path") or meta.get("source")
        if counts.get(key, 0) >= max_per_file:
            continue
        selected.append(item)
        counts[key] = counts.get(key, 0) + 1
        if len(selected) >= limit:
            break
    return selected


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
    use_reranking: bool = False,
    max_per_file: int | None = DEFAULT_MAX_PER_FILE,
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

    ranked_items = [
        {**combined[chunk_id], "score": round(rrf_scores.get(chunk_id, 0.0), 5)}
        for chunk_id in ranked_ids
    ]
    candidates = diversify_by_file(ranked_items, max_per_file, RERANK_POOL)

    if not use_reranking:
        return candidates[:top_k]

    return rerank(question, candidates, top_k)


def hybrid_search_code(
    db: Session,
    embeddings,
    question: str,
    project_id: int,
    top_k: int = 5,
    rrf_k: int = RRF_K,
    use_reranking: bool = False,
    max_per_file: int | None = DEFAULT_MAX_PER_FILE,
) -> list[dict]:
    vector_store = get_code_vector_store(embeddings)
    return _hybrid_search(
        db,
        vector_store,
        question,
        top_k,
        project_id=project_id,
        source_type="code",
        rrf_k=rrf_k,
        use_reranking=use_reranking,
        max_per_file=max_per_file,
    )


def hybrid_search_docs(
    db: Session,
    embeddings,
    question: str,
    top_k: int = 5,
    rrf_k: int = RRF_K,
    use_reranking: bool = False,
    max_per_file: int | None = DEFAULT_MAX_PER_FILE,
) -> list[dict]:
    vector_store = get_docs_vector_store(embeddings)
    return _hybrid_search(
        db,
        vector_store,
        question,
        top_k,
        source_type="official_doc",
        rrf_k=rrf_k,
        use_reranking=use_reranking,
        max_per_file=max_per_file,
    )
