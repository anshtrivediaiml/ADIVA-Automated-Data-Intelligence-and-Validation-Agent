"""
Request tracing and security middleware.
"""

from time import perf_counter
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

import config
from logger import logger
from observability import runtime_metrics


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request id to each request and emit one completion log line."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(config.REQUEST_ID_HEADER) or uuid4().hex
        request.state.request_id = request_id

        start = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (perf_counter() - start) * 1000
            logger.exception(
                f"Unhandled request failure | request_id={request_id} "
                f"method={request.method} path={request.url.path} duration_ms={duration_ms:.2f}"
            )
            raise

        duration_ms = (perf_counter() - start) * 1000
        response.headers[config.REQUEST_ID_HEADER] = request_id
        runtime_metrics.record_request(
            path=request.url.path,
            method=request.method,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        logger.info(
            f"Request completed | request_id={request_id} method={request.method} "
            f"path={request.url.path} status_code={response.status_code} duration_ms={duration_ms:.2f}"
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply a small set of safe default headers to API responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        if not config.ENABLE_SECURITY_HEADERS:
            return response

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()"
        )

        if request.url.path.startswith("/api/auth"):
            response.headers.setdefault("Cache-Control", "no-store")

        if request.url.scheme == "https" and config.HSTS_MAX_AGE_SECONDS > 0:
            response.headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={config.HSTS_MAX_AGE_SECONDS}; includeSubDomains"
            )

        return response
