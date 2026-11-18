"""Session auth helpers. Password hashes live in user_credential, not AppUser."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.i18n import SUPPORTED_LANGS
from app.models import AppUser, UserCredential

SESSION_USER_KEY = "user_id"
SESSION_LANG_KEY = "lang"
_ALGO = "pbkdf2_sha256"


class Forbidden(Exception):
    def __init__(self, message_key: str = "forbidden"):
        self.message_key = message_key


def _pbkdf2(password: str, salt: bytes, rounds: int, length: int = 32) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds, dklen=length)


def hash_password(password: str, iterations: Optional[int] = None) -> str:
    rounds = iterations or get_settings().pbkdf2_iterations
    salt = secrets.token_bytes(16)
    b64 = lambda raw: base64.b64encode(raw).decode("ascii")  # noqa: E731
    return f"{_ALGO}${rounds}${b64(salt)}${b64(_pbkdf2(password, salt, rounds))}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algo, rounds, salt, digest = stored_hash.split("$")
        expected = base64.b64decode(digest)
        candidate = _pbkdf2(password, base64.b64decode(salt), int(rounds), len(expected))
    except (ValueError, TypeError, OverflowError):
        return False
    return algo == _ALGO and hmac.compare_digest(candidate, expected)


# Verified against when the login is unknown so timing does not reveal valid emails.
_DUMMY_HASH = hash_password(secrets.token_hex(16))


def authenticate(db: Session, email: str, password: str) -> Optional[AppUser]:
    """Return the active user on success. Same failure for unknown email and bad password."""
    creds = db.scalar(
        select(UserCredential)
        .join(AppUser, UserCredential.user_id == AppUser.id)
        .where(AppUser.active.is_(True), AppUser.email == email.strip().lower())
    )
    if creds is None:
        verify_password(password, _DUMMY_HASH)
        return None
    return creds.user if verify_password(password, creds.password_hash) else None


def require_user(request: Request, db: Session = Depends(get_db)) -> AppUser:
    """Session user or JSON 401 (the SPA reacts by showing the login screen)."""
    user_id = request.session.get(SESSION_USER_KEY)
    user = db.scalar(select(AppUser).where(AppUser.id == user_id, AppUser.active.is_(True))) if user_id else None
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_roles(*roles: str) -> Callable[..., AppUser]:
    def _dependency(user: AppUser = Depends(require_user)) -> AppUser:
        if user.role not in roles:
            raise Forbidden()
        return user

    return _dependency


def get_lang(request: Request) -> str:
    """Session choice (``POST /api/lang``), else ``Accept-Language``, else English."""
    stored = request.session.get(SESSION_LANG_KEY)
    if stored in SUPPORTED_LANGS:
        return stored
    for part in (request.headers.get("accept-language") or "").lower().split(","):
        if part.split(";")[0].strip()[:2] in SUPPORTED_LANGS:
            return part.strip()[:2]
    return "en"


def set_lang(request: Request, lang: str) -> None:
    request.session[SESSION_LANG_KEY] = lang if lang in SUPPORTED_LANGS else "en"
