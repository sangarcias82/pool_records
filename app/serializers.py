"""ORM objects -> JSON dicts (snake_case; ``frontend/src/api/types.ts`` mirrors them)."""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.models import AppUser, Client, Measurement, NormRule, Pool, WaterParameter
from app.utils import iso_utc


def user(u: AppUser, lang: str = "en") -> dict[str, Any]:
    return {
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role,
        # timezone: the zone the SPA shows times in (same as the dashboard windows and folio dates)
        "organization": {"id": u.organization_id, "name": u.organization.name, "timezone": get_settings().timezone},
        "lang": lang,
        "can": u.capabilities(),
    }


def pool(p: Pool) -> dict[str, Any]:
    fields = ("id", "client_id", "name", "volume_liters", "environment")
    return {**{f: getattr(p, f) for f in fields}, "client_name": p.client.name}


def client(c: Client, *, with_pools: bool = False) -> dict[str, Any]:
    fields = ("id", "name", "contact_name", "email", "phone", "address")
    data = {**{f: getattr(c, f) for f in fields}, "pool_count": len(c.pools)}
    if with_pools:
        data["pools"] = [pool(p) for p in c.pools]
    return data


def parameter(p: WaterParameter) -> dict[str, Any]:
    fields = ("id", "code", "name", "unit", "decimals", "physical_min", "physical_max", "sort_order", "active")
    return {f: getattr(p, f) for f in fields}


def norm_rule(r: NormRule) -> dict[str, Any]:
    fields = ("id", "parameter_id", "min_value", "max_value", "classification", "source_notes", "active")
    return {
        **{f: getattr(r, f) for f in fields},
        "parameter_code": r.parameter.code,
        "parameter_name": r.parameter.name,
        "unit": r.parameter.unit,
        "decimals": r.parameter.decimals,
        "updated_at": iso_utc(r.updated_at),
        "updated_by_name": r.updated_by.full_name if r.updated_by else None,
    }


def measurement(m: Measurement) -> dict[str, Any]:
    fields = (
        "id", "folio", "pool_id", "parameter_id", "value", "unit", "notes", "recorded_by_id",
        "status", "direction", "rule_id", "rule_min", "rule_max", "rule_classification",
    )
    return {
        **{f: getattr(m, f) for f in fields},
        "pool_name": m.pool.name,
        "client_id": m.pool.client_id,
        "client_name": m.pool.client.name,
        "parameter_code": m.parameter.code,
        "parameter_name": m.parameter.name,
        "decimals": m.parameter.decimals,
        "measured_at": iso_utc(m.measured_at),
        "recorded_at": iso_utc(m.recorded_at),
        "recorded_by_name": m.recorded_by.full_name,
    }
