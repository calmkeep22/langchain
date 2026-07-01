from fastapi import APIRouter

from app.schemas.common import SuccessResponse, new_request_id

router = APIRouter()


@router.get("/health")
def get_health() -> SuccessResponse:
    return SuccessResponse(
        data={"status": "UP", "service": "rag-code-reviewer"},
        request_id=new_request_id(),
    )
