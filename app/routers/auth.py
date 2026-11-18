from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import serializers
from app.auth import SESSION_USER_KEY, authenticate, get_lang, require_user, set_lang
from app.db import get_db
from app.i18n import t
from app.models import AppUser
from app.schemas import LoginIn

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)) -> dict:
    if body.lang:
        set_lang(request, body.lang)
    found = authenticate(db, body.login, body.password)
    if found is None:
        raise HTTPException(status_code=401, detail=t(get_lang(request), "login.invalid"))
    request.session[SESSION_USER_KEY] = found.id
    return serializers.user(found, get_lang(request))


@router.post("/logout", status_code=204)
def logout(request: Request) -> None:
    request.session.pop(SESSION_USER_KEY, None)


@router.get("/me")
def me(request: Request, user: AppUser = Depends(require_user)) -> dict:
    return serializers.user(user, get_lang(request))
