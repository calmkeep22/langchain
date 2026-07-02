from typing import Generic, TypeVar
from uuid import uuid4

from pydantic import BaseModel

from app.core.request_context import get_request_id

T = TypeVar("T")


def new_request_id() -> str:
    return f"req_{uuid4().hex[:12]}"


def current_request_id() -> str:
    """The request_id assigned to the in-flight request, if any, else a fresh one.

    Response bodies must carry the same request_id as the request's logs and
    the X-Request-ID response header, so this should be used instead of
    ``new_request_id()`` everywhere a response is built inside a request.
    """
    return get_request_id() or new_request_id()


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail
    request_id: str


class SuccessResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T
    request_id: str
