"""Demo organization, users, clients and pools. Idempotent: runs only on an empty DB."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.config import get_settings
from app.models import (
    ROLE_ORG_ADMIN,
    ROLE_SUPERVISOR,
    ROLE_TECHNICIAN,
    AppUser,
    Client,
    Organization,
    Pool,
    UserCredential,
)

DEMO_USERS = [
    ("admin@aquacontrol.example", "Alicia Navarro", ROLE_ORG_ADMIN),
    ("supervisor@aquacontrol.example", "Sergio Valdés", ROLE_SUPERVISOR),
    ("tech@aquacontrol.example", "Tomás Herrera", ROLE_TECHNICIAN),
]


def seed_if_empty(db: Session) -> None:
    if db.scalar(select(func.count()).select_from(Organization)):
        return
    org = Organization(name="Laguna Azul Servicios", slug="laguna-azul")
    db.add(org)
    db.flush()
    for email, full_name, role in DEMO_USERS:
        user = AppUser(organization_id=org.id, email=email, full_name=full_name, role=role)
        user.credential = UserCredential(password_hash=hash_password(get_settings().demo_password))
        db.add(user)

    club = Client(organization_id=org.id, name="Club Deportivo Las Palmas", contact_name="Marta Ruiz",
                  email="admin@laspalmas.example", phone="555-0101", address="Av. Reforma 120")
    hotel = Client(organization_id=org.id, name="Hotel Brisa Marina", contact_name="Luis Ortega",
                   email="mantenimiento@brisa.example", phone="555-0102", address="Costera 45")
    db.add_all([club, hotel])
    db.flush()
    db.add_all([
        Pool(organization_id=org.id, client_id=club.id, name="Semiolímpica", volume_liters=375000, environment="OUTDOOR"),
        Pool(organization_id=org.id, client_id=hotel.id, name="Alberca infantil", volume_liters=18000, environment="INDOOR"),
    ])
    db.commit()
