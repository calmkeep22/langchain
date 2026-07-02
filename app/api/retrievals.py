from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.errors import ServiceError, service_error_response
from app.db.session import get_db
from app.schemas.common import SuccessResponse, current_request_id
from app.services.retrieval_service import get_retrievals

router = APIRouter()


@router.get("/retrievals/{review_id}")
def read_retrievals(review_id: int, db: Session = Depends(get_db)):
    try:
        result = get_retrievals(db, review_id)
    except ServiceError as exc:
        return service_error_response(exc)

    return SuccessResponse(data=result, request_id=current_request_id())
