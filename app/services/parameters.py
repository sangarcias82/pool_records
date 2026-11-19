"""Water parameter catalog (global reference data, shared by every organization)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import WaterParameter


def list_parameters(db: Session, *, include_inactive: bool = False) -> list[WaterParameter]:
    """Catalog in display order (``sort_order``, then ``code``). Inactive parameters only on request."""
    stmt = select(WaterParameter).order_by(WaterParameter.sort_order, WaterParameter.code)
    if not include_inactive:
        stmt = stmt.where(WaterParameter.active.is_(True))
    return list(db.scalars(stmt))
