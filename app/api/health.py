from fastapi import APIRouter

from app.schemas.common import SuccessResponse, current_request_id

router = APIRouter()


@router.get("/health")
def get_health() -> SuccessResponse:
    return SuccessResponse(
        data={"status": "UP", "service": "rag-code-reviewer"},
        request_id=current_request_id(),
    )
