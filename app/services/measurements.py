"""Measurements: capture one parameter value for a pool; evaluated against the norm rule ONCE, at creation.

There is no update path: status, direction and the rule snapshot are written here and never recomputed, so
editing a norm rule later does not change past measurements.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.models import STATUSES, Measurement, NormRule, Pool, WaterParameter
from app.services import pools as pool_service
from app.services.evaluation import evaluate
from app.services.scoping import get_owned, scoped_select
from app.utils import BusinessError, Localized, clean_text, parse_float, parse_id, to_utc_naive, utc_now

FOLIO_PREFIX = "MES"
FUTURE_TOLERANCE = timedelta(minutes=5)  # device clocks drift; anything later is rejected as future
MAX_FOLIO_ATTEMPTS = 3
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
# Explicit ISO 8601 subset so every supported Python parses the same inputs (3.11+ fromisoformat alone also takes
# "20250601" or date-only strings). Time required; seconds, 3/6-digit fractions and Z/±HH:MM offset optional.
_ISO_DATETIME = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d{3}|\.\d{6})?)?(Z|[+-]\d{2}:\d{2})?")


def folio_date(recorded_at: datetime, zone: str) -> str:
    """``YYYYMMDD`` of ``recorded_at`` (aware) in the organization's zone."""
    return recorded_at.astimezone(ZoneInfo(zone)).strftime("%Y%m%d")


def format_folio(day: str, seq: int) -> str:
    """``MES-20250601-0001``; the counter keeps growing past 9999 rather than failing a capture."""
    return f"{FOLIO_PREFIX}-{day}-{seq:04d}"


def _next_seq(db: Session, org_id: int, day: str) -> int:
    current = db.scalar(
        select(func.max(Measurement.folio_seq)).where(Measurement.organization_id == org_id, Measurement.folio_date == day)
    )
    return (current or 0) + 1


def _pool(db: Session, org_id: int, raw: Any) -> Pool:
    pool_id = parse_id(raw)
    if pool_id is None:
        raise BusinessError("err.pool")
    return pool_service.get_pool(db, org_id, pool_id)  # another organization's pool -> 404 like a missing one


def _parameter(db: Session, raw: Any) -> WaterParameter:
    parameter_id = parse_id(raw)
    parameter = db.get(WaterParameter, parameter_id) if parameter_id else None
    if parameter is None or not parameter.active:
        raise BusinessError("err.parameter")
    return parameter


def _value(raw: Any, parameter: WaterParameter) -> float:
    value = parse_float(raw)  # "7,4" and "7.4"
    if value is None:
        raise BusinessError("err.value")
    below = parameter.physical_min is not None and value < parameter.physical_min
    above = parameter.physical_max is not None and value > parameter.physical_max
    if below or above:  # impossible reading (typo), not an out-of-norm one
        raise BusinessError(
            "err.rule_range", value=f"{value:g}", parameter=Localized(f"param.{parameter.code}", parameter.name)
        )
    return value


def _unit(raw: Any, parameter: WaterParameter) -> Optional[str]:
    """Optional in the body; if sent it must be the parameter's unit (no conversions). Stored as the catalog unit."""
    sent = raw.strip() if isinstance(raw, str) else raw
    if sent not in (None, "") and (not isinstance(sent, str) or sent.casefold() != (parameter.unit or "").casefold()):
        raise BusinessError("err.unit", unit=sent, expected=parameter.unit or "-")
    return parameter.unit


def parse_iso_datetime(raw: Any) -> datetime:
    """ISO 8601 with a time (``2025-06-01T08:30:00-06:00`` or ``...Z``) -> naive UTC; no offset means UTC."""
    text = raw.strip() if isinstance(raw, str) else ""
    if not _ISO_DATETIME.fullmatch(text):
        raise BusinessError("err.measured_at")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:  # right shape, impossible date such as 2025-13-40
        raise BusinessError("err.measured_at") from None
    return to_utc_naive(parsed)


def _measured_at(raw: Any, now: datetime) -> datetime:
    """``parse_iso_datetime``; missing means now; more than ``FUTURE_TOLERANCE`` ahead is rejected."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return to_utc_naive(now)
    stored = parse_iso_datetime(raw)
    if stored > to_utc_naive(now + FUTURE_TOLERANCE):
        raise BusinessError("err.measured_future")
    return stored


def active_rule(db: Session, org_id: int, parameter_id: int) -> Optional[NormRule]:
    """The organization's active rule for the parameter, or ``None`` (-> NO_RULE)."""
    return db.scalar(
        scoped_select(NormRule, org_id).where(NormRule.parameter_id == parameter_id, NormRule.active.is_(True))
    )


def create_measurement(
    db: Session,
    org_id: int,
    data: dict[str, Any],
    user_id: int,
    *,
    now: Optional[Callable[[], datetime]] = None,
    next_seq: Callable[[Session, int, str], int] = _next_seq,
) -> Measurement:
    """Validate, evaluate against the active rule, assign the next folio of the day and save.

    ``now`` and ``next_seq`` are injectable for tests (day boundaries, forced folio collisions). Two concurrent
    captures may read the same max; the unique constraint plus a retry resolves it.
    """
    pool = _pool(db, org_id, data.get("pool_id"))
    parameter = _parameter(db, data.get("parameter_id"))
    value = _value(data.get("value"), parameter)
    unit = _unit(data.get("unit"), parameter)
    recorded_at = (now or utc_now)().astimezone(timezone.utc)
    measured_at = _measured_at(data.get("measured_at"), recorded_at)
    notes = clean_text(data.get("notes"), 500)
    day = folio_date(recorded_at, get_settings().timezone)

    result = evaluate(value, active_rule(db, org_id, parameter.id))
    fields = {
        "organization_id": org_id,
        "pool_id": pool.id,
        "parameter_id": parameter.id,
        "value": value,
        "unit": unit,
        "measured_at": measured_at,
        "notes": notes,
        "recorded_at": to_utc_naive(recorded_at),
        "recorded_by_id": user_id,
        "folio_date": day,
        "status": result.status,
        "direction": result.direction,
        "rule_id": result.rule_id,
        "rule_min": result.rule_min,
        "rule_max": result.rule_max,
        "rule_classification": result.rule_classification,
    }
    for attempt in range(1, MAX_FOLIO_ATTEMPTS + 1):
        seq = next_seq(db, org_id, day)
        measurement = Measurement(**fields, folio_seq=seq, folio=format_folio(day, seq))
        db.add(measurement)
        try:
            db.commit()
            return measurement
        except IntegrityError:
            db.rollback()
            if attempt == MAX_FOLIO_ATTEMPTS:
                raise
    raise AssertionError("unreachable")  # pragma: no cover


def get_measurement(db: Session, org_id: int, measurement_id: int) -> Measurement:
    return get_owned(db, Measurement, org_id, measurement_id)


def list_measurements(
    db: Session,
    org_id: int,
    *,
    pool_id: Optional[int] = None,
    parameter_id: Optional[int] = None,
    status: Optional[str] = None,
    measured_from: Optional[str] = None,
    limit: int = DEFAULT_LIMIT,
) -> list[Measurement]:
    """Newest first (``measured_at``, then id). Filters are optional and combine with AND.

    ``measured_from`` (ISO 8601, inclusive) matches the dashboard windows (``windows.today_from`` ...).
    """
    stmt = (
        scoped_select(Measurement, org_id)
        .options(
            joinedload(Measurement.pool).joinedload(Pool.client),
            joinedload(Measurement.parameter),
            joinedload(Measurement.recorded_by),
        )
        .order_by(Measurement.measured_at.desc(), Measurement.id.desc())
        .limit(max(1, min(limit, MAX_LIMIT)))
    )
    if pool_id is not None:
        stmt = stmt.where(Measurement.pool_id == pool_id)
    if parameter_id is not None:
        stmt = stmt.where(Measurement.parameter_id == parameter_id)
    if measured_from:
        stmt = stmt.where(Measurement.measured_at >= parse_iso_datetime(measured_from))
    if status:
        if status.strip().upper() not in STATUSES:
            raise BusinessError("err.status_filter")
        stmt = stmt.where(Measurement.status == status.strip().upper())
    return list(db.scalars(stmt))
