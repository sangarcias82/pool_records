from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.models import Client
from app.services.scoping import get_owned, scoped_select
from app.utils import BusinessError, clean_text

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean(data: dict) -> dict:
    values = {
        "name": clean_text(data.get("name"), 160),
        "contact_name": clean_text(data.get("contact_name"), 160),
        "email": (clean_text(data.get("email"), 160) or "").lower() or None,
        "phone": clean_text(data.get("phone"), 40),
        "address": clean_text(data.get("address"), 255),
    }
    if not values["name"]:
        raise BusinessError("err.client_name")
    if values["email"] and not _EMAIL_RE.match(values["email"]):
        raise BusinessError("err.email")
    return values


def list_clients(db: Session, org_id: int) -> list[Client]:
    return list(db.scalars(scoped_select(Client, org_id).order_by(Client.name)))


def get_client(db: Session, org_id: int, client_id: int) -> Client:
    return get_owned(db, Client, org_id, client_id)


def create_client(db: Session, org_id: int, data: dict) -> Client:
    client = Client(organization_id=org_id, **_clean(data))
    db.add(client)
    db.commit()
    return client
