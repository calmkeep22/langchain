import logging

from fastapi.responses import JSONResponse

from app.core.logging import log_event
from app.core.request_context import get_request_path
from app.schemas.common import ErrorDetail, ErrorResponse, current_request_id


class ServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def service_error_response(exc: ServiceError) -> JSONResponse:
    log_event(
        "error_occurred",
        level=logging.ERROR,
        error_code=exc.code,
        message=exc.message,
        path=get_request_path(),
        status_code=exc.status_code,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=ErrorDetail(code=exc.code, message=exc.message),
            request_id=current_request_id(),
        ).model_dump(),
    )
