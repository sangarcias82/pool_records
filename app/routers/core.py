"""Health probe, language preference and the dashboard (numbers come from services/dashboard.py)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth import require_user, set_lang
from app.config import get_settings
from app.db import get_db
from app.models import AppUser
from app.schemas import LangIn
from app.services import dashboard as dashboard_service

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
    """Counts plus measurement widgets: today and out of range in the last 7 days (organization time zone)."""
    return dashboard_service.dashboard(db, user.organization_id)
