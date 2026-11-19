"""Organization scoping shared by every service.

Any model with ``organization_id`` must be read through these helpers so a missing filter can never leak
another organization's rows. Global catalogs (``WaterParameter``) have no ``organization_id`` and are rejected.
"""

from __future__ import annotations

from typing import Any, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.utils import BusinessError

ModelT = TypeVar("ModelT")


def _require_scoped(model: type[Any]) -> None:
    if not hasattr(model, "organization_id"):
        raise TypeError(f"{model.__name__} is not organization-scoped")


def scoped_select(model: type[ModelT], org_id: int) -> Select[tuple[ModelT]]:
    """``SELECT model WHERE organization_id = org_id``; chain ``.where`` / ``.order_by`` / ``.options``."""
    _require_scoped(model)
    return select(model).where(model.organization_id == org_id)  # type: ignore[attr-defined]


def get_owned(db: Session, model: type[ModelT], org_id: int, record_id: int) -> ModelT:
    """Row by primary key if it belongs to ``org_id``.

    Missing and foreign rows raise the same ``BusinessError("err.not_found")`` (HTTP 404), so ids from
    other organizations cannot be probed.
    """
    _require_scoped(model)
    record = db.get(model, record_id)
    if record is None or record.organization_id != org_id:  # type: ignore[attr-defined]
        raise BusinessError("err.not_found")
    return record
