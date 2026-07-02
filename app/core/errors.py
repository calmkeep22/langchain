from fastapi.responses import JSONResponse

from app.schemas.common import ErrorDetail, ErrorResponse, new_request_id


class ServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def service_error_response(exc: ServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=ErrorDetail(code=exc.code, message=exc.message),
            request_id=new_request_id(),
        ).model_dump(),
    )
