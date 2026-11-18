from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import serializers
from app.auth import require_roles, require_user
from app.db import get_db
from app.models import ROLE_ORG_ADMIN, ROLE_SUPERVISOR, AppUser
from app.schemas import ClientIn, PoolIn
from app.services import clients as client_service
from app.services import pools as pool_service

router = APIRouter(prefix="/api/clients", tags=["clients"])
manager = require_roles(ROLE_ORG_ADMIN, ROLE_SUPERVISOR)


@router.get("")
def list_clients(user: AppUser = Depends(require_user), db: Session = Depends(get_db)) -> list[dict]:
    return [serializers.client(c) for c in client_service.list_clients(db, user.organization_id)]


@router.post("", status_code=201)
def create_client(body: ClientIn, user: AppUser = Depends(manager), db: Session = Depends(get_db)) -> dict:
    return serializers.client(client_service.create_client(db, user.organization_id, body.model_dump()))


@router.get("/{client_id}")
def get_client(client_id: int, user: AppUser = Depends(require_user), db: Session = Depends(get_db)) -> dict:
    return serializers.client(client_service.get_client(db, user.organization_id, client_id), with_pools=True)


@router.post("/{client_id}/pools", status_code=201)
def create_pool(client_id: int, body: PoolIn, user: AppUser = Depends(manager), db: Session = Depends(get_db)) -> dict:
    return serializers.pool(pool_service.create_pool(db, user.organization_id, client_id, body.model_dump()))
