from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import serializers
from app.auth import require_user
from app.db import get_db
from app.models import AppUser
from app.services import pools as pool_service

router = APIRouter(prefix="/api/pools", tags=["pools"])


@router.get("")
def list_pools(
    client_id: Optional[int] = None, user: AppUser = Depends(require_user), db: Session = Depends(get_db)
) -> list[dict]:
    return [serializers.pool(p) for p in pool_service.list_pools(db, user.organization_id, client_id)]


@router.get("/{pool_id}")
def get_pool(pool_id: int, user: AppUser = Depends(require_user), db: Session = Depends(get_db)) -> dict:
    return serializers.pool(pool_service.get_pool(db, user.organization_id, pool_id))

