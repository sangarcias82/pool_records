"""Read-only water parameter catalog. Any signed-in user may read it (the capture form needs it)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import serializers
from app.auth import require_user
from app.db import get_db
from app.models import AppUser
from app.services import parameters as parameter_service

router = APIRouter(prefix="/api/parameters", tags=["parameters"])


@router.get("")
def list_parameters(
    include_inactive: bool = False, _user: AppUser = Depends(require_user), db: Session = Depends(get_db)
) -> list[dict]:
    """Active parameters ordered by ``sort_order``; ``?include_inactive=true`` adds deactivated ones."""
    return [serializers.parameter(p) for p in parameter_service.list_parameters(db, include_inactive=include_inactive)]
