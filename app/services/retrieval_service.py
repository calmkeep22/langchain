from sqlalchemy.orm import Session

from app.core.errors import ServiceError
from app.models.chunk import Chunk
from app.models.retrieval_log import RetrievalLog
from app.models.review import Review


def get_retrievals(db: Session, review_id: int) -> dict:
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise ServiceError("REVIEW_NOT_FOUND", "Review not found.", 404)

    logs = (
        db.query(RetrievalLog)
        .filter(RetrievalLog.review_id == review_id)
        .order_by(RetrievalLog.source_type, RetrievalLog.rank)
        .all()
    )

    retrieved_chunks = []
    for log in logs:
        chunk = db.query(Chunk).filter(Chunk.id == log.chunk_id).first() if log.chunk_id else None
        retrieved_chunks.append(
            {
                "rank": log.rank,
                "source_type": log.source_type,
                "source": log.source,
                "score": log.score,
                "preview": chunk.content_preview if chunk else None,
            }
        )

    return {"review_id": review_id, "retrieved_chunks": retrieved_chunks}
