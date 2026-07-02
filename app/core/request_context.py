import contextvars

_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
_request_path_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_path", default=None
)


def set_request_id(request_id: str) -> None:
    _request_id_var.set(request_id)


def get_request_id() -> str | None:
    return _request_id_var.get()


def set_request_path(path: str) -> None:
    _request_path_var.set(path)


def get_request_path() -> str | None:
    return _request_path_var.get()
