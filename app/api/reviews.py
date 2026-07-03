from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.errors import ServiceError, service_error_response
from app.db.session import get_db
from app.schemas.common import SuccessResponse, current_request_id
from app.schemas.review import ReviewCreateRequest
from app.services.review_service import create_review, get_review, list_reviews

router = APIRouter()


@router.post("/reviews")
def create_review_endpoint(payload: ReviewCreateRequest, db: Session = Depends(get_db)):
    try:
        result = create_review(
            db,
            project_id=payload.project_id,
            question=payload.question,
            code_top_k=payload.code_top_k,
            doc_top_k=payload.doc_top_k,
        )
    except ServiceError as exc:
        return service_error_response(exc)

    return SuccessResponse(data=result, request_id=current_request_id())


@router.get("/reviews/{review_id}")
def read_review(review_id: int, db: Session = Depends(get_db)):
    try:
        review = get_review(db, review_id)
    except ServiceError as exc:
        return service_error_response(exc)

    return SuccessResponse(
        data={
            "review_id": review.id,
            "project_id": review.project_id,
            "question": review.question,
            "answer": review.answer,
            "created_at": review.created_at.isoformat(),
        },
        request_id=current_request_id(),
    )


@router.get("/projects/{project_id}/reviews")
def list_reviews_endpoint(project_id: int, db: Session = Depends(get_db)):
    reviews = list_reviews(db, project_id)
    return SuccessResponse(
        data=[
            {
                "review_id": review.id,
                "question": review.question,
                "verdict": review.verdict,
                "created_at": review.created_at.isoformat(),
            }
            for review in reviews
        ],
        request_id=current_request_id(),
    )
