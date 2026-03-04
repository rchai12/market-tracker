"""Structured JSON logging configuration.

Provides a JSON formatter and setup function for consistent log output
across FastAPI and Celery workers. Request ID correlation is available
via the `request_id_var` context variable.
"""

import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

# Context variable for request-scoped correlation ID.
# Set by RequestLoggingMiddleware (middleware.py) for HTTP requests.
# Importable by any module that needs to include request_id in logs.
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON for structured log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = request_id_var.get()
        if request_id:
            log_entry["request_id"] = request_id

        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Avoid json import overhead — manual serialization for simple dict
        parts = []
        for key, value in log_entry.items():
            if isinstance(value, str):
                escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
                parts.append(f'"{key}": "{escaped}"')
            else:
                parts.append(f'"{key}": {value}')
        return "{" + ", ".join(parts) + "}"


def setup_logging(log_level: str = "INFO") -> None:
    """Configure root logger with JSON formatter.

    Call once at startup — in FastAPI lifespan and Celery worker_process_init.
    All loggers using ``logging.getLogger(__name__)`` inherit this config.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Quiet noisy third-party loggers
    for name in ("uvicorn.access", "httpx", "httpcore", "watchfiles"):
        logging.getLogger(name).setLevel(logging.WARNING)
