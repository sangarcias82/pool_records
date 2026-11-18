"""Health probe, language preference and the dashboard counts."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_user, set_lang
from app.config import get_settings
from app.db import get_db
from app.models import AppUser, Client, Pool
from app.schemas import LangIn

router = APIRouter(prefix="/api", tags=["core"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": get_settings().app_name}


@router.post("/lang")
def choose_language(body: LangIn, request: Request) -> dict[str, str]:
    set_lang(request, body.lang)
    return {"lang": request.session["lang"]}


@router.get("/dashboard")
def dashboard(user: AppUser = Depends(require_user), db: Session = Depends(get_db)) -> dict:
    def count(model) -> int:
        return db.scalar(select(func.count()).select_from(model).where(model.organization_id == user.organization_id)) or 0

    return {"counts": {"clients": count(Client), "pools": count(Pool), "users": count(AppUser)}}
