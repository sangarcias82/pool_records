"""JSON error handlers: translated, with a stable ``key`` the SPA can rely on."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.auth import Forbidden, get_lang
from app.utils import BusinessError
from app.i18n import t


def error_response(status_code: int, detail: str, **extra: Any) -> JSONResponse:
    return JSONResponse({"detail": detail, **extra}, status_code=status_code)


async def business_error_handler(request: Request, exc: BusinessError) -> JSONResponse:
    """404 for a missing record, 422 for every other rule violation."""
    status = 404 if exc.key == "err.not_found" else 422
    return error_response(status, t(get_lang(request), exc.key, **exc.params), key=exc.key)


async def forbidden_handler(request: Request, exc: Forbidden) -> JSONResponse:
    return error_response(403, t(get_lang(request), exc.message_key), key=exc.message_key)


async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(422, t(get_lang(request), "err.required"), key="err.required")
