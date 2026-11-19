"""JSON error handlers: translated, with a stable ``key`` the SPA can rely on."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.auth import Forbidden, Unauthenticated, get_lang
from app.i18n import t
from app.utils import BusinessError, Localized


def error_response(status_code: int, detail: str, **extra: Any) -> JSONResponse:
    return JSONResponse({"detail": detail, **extra}, status_code=status_code)


def _param_text(lang: str, value: object) -> str:
    if isinstance(value, Localized):
        text = t(lang, value.key)
        return value.fallback if text == value.key else text
    return str(value)


async def business_error_handler(request: Request, exc: BusinessError) -> JSONResponse:
    """404 for a missing record, 422 for every other rule violation."""
    lang = get_lang(request)
    status = 404 if exc.key == "err.not_found" else 422
    params = {name: _param_text(lang, value) for name, value in exc.params.items()}
    return error_response(status, t(lang, exc.key, **params), key=exc.key)


async def unauthenticated_handler(request: Request, exc: Unauthenticated) -> JSONResponse:
    """401: no valid session, or wrong credentials on login. The SPA shows the login screen."""
    return error_response(401, t(get_lang(request), exc.message_key), key=exc.message_key)


async def forbidden_handler(request: Request, exc: Forbidden) -> JSONResponse:
    return error_response(403, t(get_lang(request), exc.message_key), key=exc.message_key)


async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(422, t(get_lang(request), "err.required"), key="err.required")
