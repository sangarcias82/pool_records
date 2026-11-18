from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import ENVIRONMENTS, Pool
from app.services import clients as client_service
from app.utils import BusinessError, clean_text, parse_float

MAX_VOLUME_LITERS = 100_000_000


def _clean(data: dict) -> dict:
    name = clean_text(data.get("name"), 160)
    if not name:
        raise BusinessError("err.pool_name")
    volume = parse_float(data.get("volume_liters"))
    if volume is None or volume <= 0 or volume > MAX_VOLUME_LITERS:
        raise BusinessError("err.volume")
    environment = (data.get("environment") or "OUTDOOR").upper()
    if environment not in ENVIRONMENTS:
        raise BusinessError("err.environment")
    return {"name": name, "volume_liters": volume, "environment": environment}


def list_pools(db: Session, org_id: int, client_id: Optional[int] = None) -> list[Pool]:
    stmt = select(Pool).options(joinedload(Pool.client)).where(Pool.organization_id == org_id).order_by(Pool.name)
    if client_id is not None:
        stmt = stmt.where(Pool.client_id == client_id)
    return list(db.scalars(stmt))


def get_pool(db: Session, org_id: int, pool_id: int) -> Pool:
    pool = db.get(Pool, pool_id)
    if pool is None or pool.organization_id != org_id:
        raise BusinessError("err.not_found")
    return pool


def create_pool(db: Session, org_id: int, client_id: int, data: dict) -> Pool:
    client = client_service.get_client(db, org_id, client_id)
    pool = Pool(organization_id=org_id, client_id=client.id, **_clean(data))
    db.add(pool)
    db.commit()
    return pool
