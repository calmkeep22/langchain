import logging
from functools import lru_cache

from app.core.config import get_settings
from app.core.logging import log_event

logger = logging.getLogger("app")


@lru_cache
def _get_ranker():
    from flashrank import Ranker

    settings = get_settings()
    return Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir=settings.flashrank_cache_dir)


def rerank(query: str, items: list[dict], top_k: int) -> list[dict]:
    """Re-score a candidate pool with a lightweight cross-encoder.

    Falls back to the pool's existing (RRF) order, truncated to ``top_k``,
    if the reranker model can't be loaded (e.g. no network on first run) --
    a review should still work, just without the reranking quality boost.
    """
    if not items:
        return []

    try:
        from flashrank import RerankRequest

        passages = [{"id": i, "text": item["text"]} for i, item in enumerate(items)]
        ranked = _get_ranker().rerank(RerankRequest(query=query, passages=passages))
    except Exception:
        log_event("reranking_failed", level=logging.WARNING, candidate_count=len(items))
        return items[:top_k]

    return [
        {**items[entry["id"]], "score": round(float(entry["score"]), 5)}
        for entry in ranked[:top_k]
    ]
