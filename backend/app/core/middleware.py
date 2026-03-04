"""ASGI middleware for request logging and correlation IDs."""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging_config import request_id_var

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Assigns a request ID and logs each HTTP request with timing.

    Sets the ``request_id_var`` context variable so downstream loggers
    automatically include the correlation ID. Also adds an
    ``X-Request-ID`` response header for client-side tracing.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = request_id_var.set(rid)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            latency_ms = round((time.perf_counter() - start) * 1000, 1)
            logger.exception(
                "request_error method=%s path=%s latency_ms=%s client=%s",
                request.method,
                request.url.path,
                latency_ms,
                request.client.host if request.client else "-",
            )
            raise
        finally:
            request_id_var.reset(token)

        latency_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.info(
            "request method=%s path=%s status=%s latency_ms=%s client=%s",
            request.method,
            request.url.path,
            response.status_code,
            latency_ms,
            request.client.host if request.client else "-",
        )

        response.headers["X-Request-ID"] = rid
        return response
