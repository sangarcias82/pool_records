"""Startup seeding, split into independent idempotent steps.

``run_seed`` runs on every start (``db.init_db``) and in tests. Each ``ensure_*`` step decides on its own
whether there is work to do, so a database created by an older version still receives catalogs added later:

- ``ensure_demo_data``: demo organization, users, clients and pools; only when there is no organization yet.
- ``ensure_parameters``: inserts catalog codes that are missing. It never updates or deletes existing rows,
  so a parameter deactivated or tuned in the database stays that way across restarts.
- ``ensure_default_rules``: gives the demo organization a planning-default norm rule for every catalog parameter
  it has no rule for. Existing rules (including admin edits) are never touched.

``create_all`` (no migrations) adds new tables to an existing database but never new columns, so features
add tables rather than altering existing ones.
"""

from __future__ import annotations

from typing import NamedTuple, Optional

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
    NormRule,
    Organization,
    Pool,
    UserCredential,
    WaterParameter,
)

DEMO_ORG_SLUG = "laguna-azul"
DEMO_USERS = [
    ("admin@aquacontrol.example", "Alicia Navarro", ROLE_ORG_ADMIN),
    ("supervisor@aquacontrol.example", "Sergio Valdés", ROLE_SUPERVISOR),
    ("tech@aquacontrol.example", "Tomás Herrera", ROLE_TECHNICIAN),
]


class ParameterSpec(NamedTuple):
    code: str
    name: str
    unit: Optional[str]
    decimals: int
    physical_min: Optional[float]
    physical_max: Optional[float]
    sort_order: int


# Physical min/max are plausibility bounds for typed values (typo guard), not regulatory limits.
# sort_order leaves gaps of 10 so later parameters can be slotted in without renumbering.
PARAMETER_CATALOG: tuple[ParameterSpec, ...] = (
    ParameterSpec("PH", "pH", None, 1, 0, 14, 10),
    ParameterSpec("FREE_CHLORINE", "Free chlorine", "mg/L", 2, 0, 20, 20),
    ParameterSpec("TOTAL_CHLORINE", "Total chlorine", "mg/L", 2, 0, 20, 30),
    ParameterSpec("COMBINED_CHLORINE", "Combined chlorine", "mg/L", 2, 0, 20, 40),
    ParameterSpec("CYANURIC_ACID", "Cyanuric acid", "mg/L", 0, 0, 300, 50),
    ParameterSpec("TURBIDITY", "Turbidity", "NTU", 1, 0, 100, 60),
    ParameterSpec("TOTAL_ALKALINITY", "Total alkalinity", "mg/L CaCO3", 0, 0, 1000, 70),
    ParameterSpec("CALCIUM_HARDNESS", "Calcium hardness", "mg/L CaCO3", 0, 0, 2000, 80),
    ParameterSpec("TEMPERATURE", "Temperature", "°C", 1, 0, 50, 90),
    ParameterSpec("TDS", "Total dissolved solids", "mg/L", 0, 0, None, 100),
)


class RuleSpec(NamedTuple):
    code: str
    min_value: Optional[float]
    max_value: Optional[float]
    classification: str
    active: bool
    source_notes: str


# source_notes are free text stored with the rule (shown as stored, not translated by the UI). The demo organization
# is Mexican, so they are Spanish like its other data; the UI shows a translated "planning default" tag for rules
# nobody edited yet (updated_at is null).
_NOM = "Valor de planeación, sin verificar: compárelo con el texto vigente de la NOM-245-SSA1-2010 antes de usarlo."
_PRACTICE = "Valor de planeación, sin verificar: práctica común de mantenimiento de albercas, no es un límite legal."

# PLANNING DEFAULTS for the demo organization. Editable by ORG_ADMIN through PATCH /api/norm-rules/{id}.
# The values and the NORMATIVE/COMPLEMENTARY split are starting points for the product, not regulatory advice.
DEFAULT_NORM_RULES: tuple[RuleSpec, ...] = (
    RuleSpec("PH", 7.2, 7.8, "NORMATIVE", True, _NOM),
    RuleSpec("FREE_CHLORINE", 1.0, 3.0, "NORMATIVE", True, _NOM),
    RuleSpec("TOTAL_CHLORINE", None, 3.5, "COMPLEMENTARY", False,
             _PRACTICE + " Inactiva: el valor que se controla es el cloro combinado."),
    RuleSpec("COMBINED_CHLORINE", None, 0.2, "NORMATIVE", True, _NOM),
    RuleSpec("CYANURIC_ACID", None, 50, "COMPLEMENTARY", True, _PRACTICE + " Principalmente albercas exteriores."),
    RuleSpec("TURBIDITY", None, 0.5, "NORMATIVE", True, _NOM),
    RuleSpec("TOTAL_ALKALINITY", 80, 120, "COMPLEMENTARY", True, _PRACTICE),
    RuleSpec("CALCIUM_HARDNESS", 200, 400, "COMPLEMENTARY", True, _PRACTICE),
    RuleSpec("TEMPERATURE", 24, 30, "COMPLEMENTARY", True, _PRACTICE),
    RuleSpec("TDS", None, 1500, "COMPLEMENTARY", False,
             _PRACTICE + " Inactiva: las albercas con clorador salino tienen valores mucho más altos."),
)


def run_seed(db: Session) -> None:
    """Every seeding step, in order. Safe to call on every startup."""
    ensure_demo_data(db)
    ensure_parameters(db)
    ensure_default_rules(db)


def ensure_demo_data(db: Session) -> bool:
    """Demo organization, users, clients and pools. Returns ``True`` if it created them."""
    if db.scalar(select(func.count()).select_from(Organization)):
        return False
    org = Organization(name="Laguna Azul Servicios", slug=DEMO_ORG_SLUG)
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
    return True


def ensure_parameters(db: Session) -> int:
    """Insert catalog parameters whose ``code`` is missing. Returns how many rows were added."""
    existing = set(db.scalars(select(WaterParameter.code)))
    missing = [spec for spec in PARAMETER_CATALOG if spec.code not in existing]
    db.add_all(WaterParameter(**spec._asdict()) for spec in missing)
    db.commit()
    return len(missing)


def ensure_default_rules(db: Session) -> int:
    """Planning-default rules for the demo organization, only for parameters it has no rule for yet.

    Returns how many rules were added. Other organizations get no defaults (multi-organization is out of scope).
    """
    org_id = db.scalar(select(Organization.id).where(Organization.slug == DEMO_ORG_SLUG))
    if org_id is None:
        return 0
    parameters = {p.code: p.id for p in db.scalars(select(WaterParameter))}
    covered = set(db.scalars(select(NormRule.parameter_id).where(NormRule.organization_id == org_id)))
    new_rules = [
        NormRule(
            organization_id=org_id,
            parameter_id=parameters[spec.code],
            **{field: value for field, value in spec._asdict().items() if field != "code"},
        )
        for spec in DEFAULT_NORM_RULES
        if spec.code in parameters and parameters[spec.code] not in covered
    ]
    db.add_all(new_rules)
    db.commit()
    return len(new_rules)
