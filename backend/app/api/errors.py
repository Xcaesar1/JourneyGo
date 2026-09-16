"""Route-aware exception handling that preserves legacy response shapes."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..domain.error_models import ErrorDetailV2, build_error_envelope

_V2_PREFIX = "/api/v2"
_LOGGER = logging.getLogger(__name__)
_STATUS_CODE_MAP = {
    400: "bad_request",
    401: "unauthorized",
    413: "request_too_large",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_server_error",
    503: "service_unavailable",
}


def is_v2_path(path: str) -> bool:
    """Return whether a path belongs to the bounded v2 API namespace."""
    return path == _V2_PREFIX or path.startswith(f"{_V2_PREFIX}/")


def _is_v2_request(request: Request) -> bool:
    """Determine whether the current request should receive a v2 envelope."""
    return is_v2_path(request.url.path)


def _normalize_http_message(detail: Any) -> str:
    """Flatten FastAPI/Starlette HTTP error detail values into a stable message."""
    if isinstance(detail, str):
        return detail
    return "HTTP error."


def _build_validation_details(exc: RequestValidationError) -> list[ErrorDetailV2]:
    """Convert FastAPI validation errors into the typed v2 detail shape."""
    details: list[ErrorDetailV2] = []
    for error in exc.errors():
        location = error.get("loc", ())
        field = ".".join(str(part) for part in location if part not in {"body", "query", "path"})
        details.append(
            ErrorDetailV2(
                field=field or None,
                message=error.get("msg", "Invalid request."),
                code=error.get("type", "validation_error"),
            )
        )
    return details


def register_api_exception_handlers(app: FastAPI) -> None:
    """Attach route-aware exception handlers to the given FastAPI app."""

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        if not _is_v2_request(request):
            return await request_validation_exception_handler(request, exc)

        payload = build_error_envelope(
            code="validation_error",
            message="Request validation failed.",
            details=_build_validation_details(exc),
        )
        return JSONResponse(status_code=422, content=payload.model_dump(mode="json"))

    @app.exception_handler(HTTPException)
    async def handle_fastapi_http(request: Request, exc: HTTPException) -> JSONResponse:
        if not _is_v2_request(request):
            return await http_exception_handler(request, exc)

        payload = build_error_envelope(
            code=_STATUS_CODE_MAP.get(exc.status_code, "http_error"),
            message=_normalize_http_message(exc.detail),
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump(mode="json"))

    @app.exception_handler(StarletteHTTPException)
    async def handle_starlette_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if not _is_v2_request(request):
            return await http_exception_handler(request, exc)

        payload = build_error_envelope(
            code=_STATUS_CODE_MAP.get(exc.status_code, "http_error"),
            message=_normalize_http_message(exc.detail),
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump(mode="json"))

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        if not _is_v2_request(request):
            raise exc

        _LOGGER.error(
            "Unhandled exception in v2 API",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        payload = build_error_envelope(
            code="internal_server_error",
            message="An unexpected server error occurred.",
        )
        return JSONResponse(status_code=500, content=payload.model_dump(mode="json"))
