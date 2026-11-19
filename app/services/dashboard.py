"""Dashboard numbers for the signed-in user's organization.

Measurement windows are calendar days in ``Settings.timezone`` (the organization's zone), not in UTC and not in
the browser's zone:

- ``today``: measured since local midnight today;
- ``out_of_range_last_7_days``: ``OUT_OF_RANGE`` measurements since local midnight six days ago (today + the six
  previous days).

The window starts are returned too, so a client can link to the matching list
(``GET /api/measurements?measured_from=<start>[&status=OUT_OF_RANGE]``) and see exactly the counted rows.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import STATUS_OUT_OF_RANGE, AppUser, Client, Measurement, Pool
from app.utils import to_utc_naive, utc_now

LAST_DAYS = 7


def _iso_z(value: datetime) -> str:
    """UTC ISO 8601 with ``Z`` (no ``+`` to escape when used in a URL)."""
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def windows(now: datetime, zone_name: str) -> dict[str, Any]:
    zone = ZoneInfo(zone_name)
    local_today = now.astimezone(zone).date()
    today_from = datetime.combine(local_today, time.min, tzinfo=zone)
    week_from = datetime.combine(local_today - timedelta(days=LAST_DAYS - 1), time.min, tzinfo=zone)
    return {"timezone": zone_name, "today_from": today_from, "last_7_days_from": week_from}


def dashboard(db: Session, org_id: int, *, now: Optional[Callable[[], datetime]] = None) -> dict[str, Any]:
    def count(model, *conditions) -> int:
        stmt = select(func.count()).select_from(model).where(model.organization_id == org_id, *conditions)
        return db.scalar(stmt) or 0

    bounds = windows((now or utc_now)(), get_settings().timezone)
    since_today = to_utc_naive(bounds["today_from"])
    since_week = to_utc_naive(bounds["last_7_days_from"])
    return {
        "counts": {"clients": count(Client), "pools": count(Pool), "users": count(AppUser)},
        "measurements": {
            "today": count(Measurement, Measurement.measured_at >= since_today),
            "out_of_range_last_7_days": count(
                Measurement, Measurement.status == STATUS_OUT_OF_RANGE, Measurement.measured_at >= since_week
            ),
        },
        "windows": {
            "timezone": bounds["timezone"],
            "today_from": _iso_z(bounds["today_from"]),
            "last_7_days_from": _iso_z(bounds["last_7_days_from"]),
        },
    }
