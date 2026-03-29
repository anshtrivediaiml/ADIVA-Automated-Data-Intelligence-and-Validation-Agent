"""
Centralized API error helpers.
"""

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

import config


def get_request_id(request: Request) -> str | None:
    """Return the request identifier if the middleware has set one."""
    return getattr(request.state, "request_id", None)


def build_error_payload(
    request: Request,
    message: str,
    *,
    detail=None,
) -> dict:
    """Build a consistent API error payload."""
    payload = {
        "status": "error",
        "message": message,
    }

    request_id = get_request_id(request)
    if request_id:
        payload["request_id"] = request_id

    if detail is not None and config.API_SHOW_ERROR_DETAILS:
        payload["detail"] = detail

    return payload


def error_response(
    request: Request,
    status_code: int,
    message: str,
    *,
    detail=None,
) -> JSONResponse:
    """Create a JSON error response with optional debug detail."""
    return JSONResponse(
        status_code=status_code,
        content=build_error_payload(request, message, detail=detail),
    )


def validation_error_response(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Return a sanitized validation error response."""
    detail = exc.errors() if config.API_SHOW_ERROR_DETAILS else None
    return error_response(
        request,
        422,
        "Invalid request payload",
        detail=detail,
    )


def internal_server_error(message: str = "Internal server error") -> HTTPException:
    """Raise a generic 500 without exposing internals to clients."""
    return HTTPException(status_code=500, detail=message)
