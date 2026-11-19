"""Measurements of the signed-in user's organization: capture (``capture_measurements``) and read (everyone)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import serializers
from app.auth import require_capability, require_user
from app.db import get_db
from app.models import AppUser
from app.schemas import MeasurementIn
from app.services import measurements as measurement_service

router = APIRouter(prefix="/api/measurements", tags=["measurements"])
capturer = require_capability("capture_measurements")


@router.post("", status_code=201)
def create_measurement(body: MeasurementIn, user: AppUser = Depends(capturer), db: Session = Depends(get_db)) -> dict:
    """Capture one value for a pool of the user's organization; gets a folio and is evaluated once, now."""
    created = measurement_service.create_measurement(db, user.organization_id, body.model_dump(), user.id)
    return serializers.measurement(created)


@router.get("")
def list_measurements(
    pool_id: Optional[int] = None,
    parameter_id: Optional[int] = None,
    status: Optional[str] = None,
    measured_from: Optional[str] = None,
    limit: int = measurement_service.DEFAULT_LIMIT,
    user: AppUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Newest first. ``status`` is OK | OUT_OF_RANGE | NO_RULE (case-insensitive); ``measured_from`` is ISO 8601
    (inclusive, e.g. the dashboard's ``windows.today_from``); ``limit`` is clamped to 1..200."""
    rows = measurement_service.list_measurements(
        db, user.organization_id, pool_id=pool_id, parameter_id=parameter_id, status=status,
        measured_from=measured_from, limit=limit
    )
    return [serializers.measurement(m) for m in rows]


@router.get("/{measurement_id}")
def get_measurement(measurement_id: int, user: AppUser = Depends(require_user), db: Session = Depends(get_db)) -> dict:
    return serializers.measurement(measurement_service.get_measurement(db, user.organization_id, measurement_id))
