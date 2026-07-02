import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from app.core.logging import log_event
from app.core.request_context import set_request_id, set_request_path
from app.db.session import SessionLocal
from app.models.request_log import RequestLog
from app.schemas.common import new_request_id


class RequestIDMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or new_request_id()
        set_request_id(request_id)
        set_request_path(request.url.path)
        request.state.request_id = request_id

        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        log_event(
            "http_request_started",
            method=request.method,
            path=request.url.path,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = int((time.perf_counter() - start) * 1000)

        log_event(
            "http_request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=latency_ms,
        )

        response.headers["X-Request-ID"] = request_id
        self._persist_request_log(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=latency_ms,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        return response

    @staticmethod
    def _persist_request_log(**fields) -> None:
        db = SessionLocal()
        try:
            db.add(RequestLog(**fields))
            db.commit()
        finally:
            db.close()
