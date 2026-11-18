"""ORM objects -> JSON dicts (snake_case; ``frontend/src/api/types.ts`` mirrors them)."""

from __future__ import annotations

from typing import Any

from app.models import AppUser, Client, Pool


def user(u: AppUser, lang: str = "en") -> dict[str, Any]:
    return {
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role,
        "organization": {"id": u.organization_id, "name": u.organization.name},
        "lang": lang,
        "can": {"manage_clients": u.can_manage_clients()},
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
