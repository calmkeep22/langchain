from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.errors import ServiceError, service_error_response
from app.db.session import get_db
from app.schemas.common import SuccessResponse, new_request_id
from app.schemas.index import IndexCodeRequest
from app.services.code_indexing_service import index_project_code

router = APIRouter()


@router.post("/index/code")
def index_code(payload: IndexCodeRequest, db: Session = Depends(get_db)):
    try:
        result = index_project_code(db, payload.project_id, payload.force_reindex)
    except ServiceError as exc:
        return service_error_response(exc)

    return SuccessResponse(data=result, request_id=new_request_id())
