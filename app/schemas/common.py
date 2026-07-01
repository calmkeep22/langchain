from typing import Generic, TypeVar
from uuid import uuid4

from pydantic import BaseModel

T = TypeVar("T")


def new_request_id() -> str:
    return f"req_{uuid4().hex[:12]}"


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
