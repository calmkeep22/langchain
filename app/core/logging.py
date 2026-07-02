import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.core.request_context import get_request_id

LOG_FILE_PATH = Path("logs/app.log")

logger = logging.getLogger("app")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "event": getattr(record, "event", record.getMessage()),
            "request_id": getattr(record, "request_id", None) or get_request_id(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        payload.update(getattr(record, "fields", {}) or {})
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(JsonFormatter())

    LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
    file_handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [stream_handler, file_handler]
    root.setLevel(logging.INFO)


def log_event(event: str, level: int = logging.INFO, **fields) -> None:
    logger.log(
        level,
        event,
        extra={"event": event, "fields": fields, "request_id": get_request_id()},
    )
