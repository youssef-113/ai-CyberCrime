import json
import logging
import contextvars
from datetime import datetime

request_id_ctx = contextvars.ContextVar("request_id", default=None)
user_id_ctx = contextvars.ContextVar("user_id", default=None)
path_ctx = contextvars.ContextVar("path", default=None)
method_ctx = contextvars.ContextVar("method", default=None)


class RequestContextFilter(logging.Filter):
    """Attach request context to all log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        record.user_id = user_id_ctx.get()
        record.path = path_ctx.get()
        record.method = method_ctx.get()
        return True


class JsonFormatter(logging.Formatter):
    """Emit logs as structured JSON for easy ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if getattr(record, "request_id", None):
            payload["request_id"] = record.request_id
        if getattr(record, "user_id", None):
            payload["user_id"] = record.user_id
        if getattr(record, "path", None):
            payload["path"] = record.path
        if getattr(record, "method", None):
            payload["method"] = record.method

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra") and isinstance(record.extra, dict):
            payload.update(record.extra)

        return json.dumps(payload, default=str)


def configure_structured_logging(level: int = logging.INFO) -> None:
    logger = logging.getLogger()
    logger.handlers = []
    handler = logging.StreamHandler()
    formatter = JsonFormatter()
    handler.setFormatter(formatter)
    handler.addFilter(RequestContextFilter())
    logger.addHandler(handler)
    logger.setLevel(level)


def set_request_context(request_id: str | None = None, user_id: str | None = None, path: str | None = None, method: str | None = None) -> None:
    request_id_ctx.set(request_id)
    user_id_ctx.set(user_id)
    path_ctx.set(path)
    method_ctx.set(method)


def clear_request_context() -> None:
    request_id_ctx.set(None)
    user_id_ctx.set(None)
    path_ctx.set(None)
    method_ctx.set(None)
