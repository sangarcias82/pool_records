"""SQLAlchemy 2 models. Every business entity carries ``organization_id``.

Exception: reference catalogs shared by all organizations (``WaterParameter``) are global on purpose;
per-organization settings about them (norm rules, later) carry ``organization_id`` instead.

Password hashes live ONLY in ``UserCredential``; ``AppUser`` is the view-facing identity.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, event, inspect
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

ROLE_ORG_ADMIN = "ORG_ADMIN"
ROLE_SUPERVISOR = "SUPERVISOR"
ROLE_TECHNICIAN = "TECHNICIAN"
ROLES = (ROLE_ORG_ADMIN, ROLE_SUPERVISOR, ROLE_TECHNICIAN)
ENVIRONMENTS = ("OUTDOOR", "INDOOR")
# NORMATIVE: limit taken from a regulation (e.g. a NOM). COMPLEMENTARY: good-practice target, not a legal limit.
CLASSIFICATIONS = ("NORMATIVE", "COMPLEMENTARY")
# Result of evaluating a measurement against its norm rule at capture time (see services/evaluation.py).
STATUS_OK = "OK"
STATUS_OUT_OF_RANGE = "OUT_OF_RANGE"
STATUS_NO_RULE = "NO_RULE"
STATUSES = (STATUS_OK, STATUS_OUT_OF_RANGE, STATUS_NO_RULE)
DIRECTION_LOW = "LOW"
DIRECTION_HIGH = "HIGH"

# Single source of truth for permissions: capability -> roles that hold it.
# Routers guard with ``require_capability(name)``; ``/api/auth/me`` exposes every flag as ``can.<name>``
# so the SPA hides actions the API would reject. Adding a permission = adding one line here.
CAPABILITIES: dict[str, frozenset[str]] = {
    "manage_clients": frozenset({ROLE_ORG_ADMIN, ROLE_SUPERVISOR}),
    "manage_norm_rules": frozenset({ROLE_ORG_ADMIN}),
    "capture_measurements": frozenset({ROLE_ORG_ADMIN, ROLE_SUPERVISOR, ROLE_TECHNICIAN}),
}


def _org_fk() -> Mapped[int]:
    return mapped_column(ForeignKey("organization.id"), nullable=False, index=True)


class Organization(Base):
    __tablename__ = "organization"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = _org_fk()
    email: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization: Mapped[Organization] = relationship()
    credential: Mapped[Optional[UserCredential]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    def can(self, capability: str) -> bool:
        """True if this user's role holds ``capability``. Unknown names raise ``KeyError`` (typo guard)."""
        return self.role in CAPABILITIES[capability]

    def capabilities(self) -> dict[str, bool]:
        return {name: self.role in roles for name, roles in CAPABILITIES.items()}


class UserCredential(Base):
    __tablename__ = "user_credential"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    user: Mapped[AppUser] = relationship(back_populates="credential")


class Client(Base):
    __tablename__ = "client"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = _org_fk()
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    contact_name: Mapped[Optional[str]] = mapped_column(String(160))
    email: Mapped[Optional[str]] = mapped_column(String(160))
    phone: Mapped[Optional[str]] = mapped_column(String(40))
    address: Mapped[Optional[str]] = mapped_column(String(255))

    pools: Mapped[list[Pool]] = relationship(back_populates="client", order_by="Pool.name")


class Pool(Base):
    """Alberca. ``volume_liters`` is authoritative."""

    __tablename__ = "pool"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = _org_fk()
    client_id: Mapped[int] = mapped_column(ForeignKey("client.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    volume_liters: Mapped[float] = mapped_column(Float, nullable=False)
    environment: Mapped[str] = mapped_column(String(10), default="OUTDOOR", nullable=False)

    client: Mapped[Client] = relationship(back_populates="pools")


class WaterParameter(Base):
    """Global catalog of measurable water parameters (pH, free chlorine, ...).

    ``code`` is the stable identifier used by the API, the SPA (``param.<CODE>`` labels) and future norm rules;
    never rename it. ``name`` is the canonical English label. ``physical_min``/``physical_max`` are plausibility
    bounds for typed values (pH cannot be 15), NOT regulatory limits: those belong to per-organization norm rules.
    ``unit`` is ``None`` for dimensionless parameters (pH).
    """

    __tablename__ = "water_parameter"
    __table_args__ = (
        CheckConstraint("decimals >= 0 AND decimals <= 4", name="ck_water_parameter_decimals"),
        CheckConstraint(
            "physical_min IS NULL OR physical_max IS NULL OR physical_min <= physical_max",
            name="ck_water_parameter_physical_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(20))
    decimals: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    physical_min: Mapped[Optional[float]] = mapped_column(Float)
    physical_max: Mapped[Optional[float]] = mapped_column(Float)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class NormRule(Base):
    """Acceptable range of one water parameter for one organization (one rule per organization + parameter).

    Either bound may be ``None`` (one-sided rule, e.g. combined chlorine <= 0.2) but not both. An inactive rule is
    kept for reference and is ignored by evaluation. ``updated_at``/``updated_by_id`` stay ``None`` until an admin
    edits the seeded planning default.
    """

    __tablename__ = "norm_rule"
    __table_args__ = (
        UniqueConstraint("organization_id", "parameter_id", name="uq_norm_rule_org_parameter"),
        CheckConstraint("min_value IS NOT NULL OR max_value IS NOT NULL", name="ck_norm_rule_has_bound"),
        CheckConstraint(
            "min_value IS NULL OR max_value IS NULL OR min_value <= max_value", name="ck_norm_rule_min_le_max"
        ),
        CheckConstraint("classification IN ('NORMATIVE', 'COMPLEMENTARY')", name="ck_norm_rule_classification"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = _org_fk()
    parameter_id: Mapped[int] = mapped_column(ForeignKey("water_parameter.id"), nullable=False, index=True)
    min_value: Mapped[Optional[float]] = mapped_column(Float)
    max_value: Mapped[Optional[float]] = mapped_column(Float)
    classification: Mapped[str] = mapped_column(String(20), default="NORMATIVE", nullable=False)
    source_notes: Mapped[Optional[str]] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)  # UTC, naive in SQLite
    updated_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("app_user.id"))

    parameter: Mapped[WaterParameter] = relationship()
    updated_by: Mapped[Optional[AppUser]] = relationship()


class Measurement(Base):
    """One captured value of one parameter in one pool.

    ``folio`` is ``MES-YYYYMMDD-####``: the local date (``Settings.timezone``) on which the row was recorded plus a
    per-organization daily counter (``folio_date`` + ``folio_seq``); unique per organization. ``unit`` is copied
    from the parameter at capture so history keeps the unit it was read in.

    Evaluation (``status``, ``direction``) and the rule snapshot (``rule_id``, ``rule_min``, ``rule_max``,
    ``rule_classification``) are written at creation and never recomputed, so later edits of the norm rule do
    not rewrite history. Times are stored as naive UTC.
    """

    __tablename__ = "measurement"
    __table_args__ = (
        UniqueConstraint("organization_id", "folio", name="uq_measurement_org_folio"),
        UniqueConstraint("organization_id", "folio_date", "folio_seq", name="uq_measurement_org_day_seq"),
        CheckConstraint("status IN ('OK', 'OUT_OF_RANGE', 'NO_RULE')", name="ck_measurement_status"),
        CheckConstraint(
            # IS NOT NULL matters: NULL IN (...) is NULL, and CHECK only rejects FALSE
            "(status = 'OUT_OF_RANGE' AND direction IS NOT NULL AND direction IN ('LOW', 'HIGH'))"
            " OR (status <> 'OUT_OF_RANGE' AND direction IS NULL)",
            name="ck_measurement_direction",
        ),
        CheckConstraint(
            "(status = 'NO_RULE' AND rule_id IS NULL AND rule_min IS NULL AND rule_max IS NULL"
            " AND rule_classification IS NULL)"
            " OR (status <> 'NO_RULE' AND rule_id IS NOT NULL)",
            name="ck_measurement_rule_snapshot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = _org_fk()
    folio: Mapped[str] = mapped_column(String(24), nullable=False)
    folio_date: Mapped[str] = mapped_column(String(8), nullable=False)  # YYYYMMDD, local date of recording
    folio_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    pool_id: Mapped[int] = mapped_column(ForeignKey("pool.id"), nullable=False, index=True)
    parameter_id: Mapped[int] = mapped_column(ForeignKey("water_parameter.id"), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(20))
    measured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    notes: Mapped[Optional[str]] = mapped_column(String(500))
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    recorded_by_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), nullable=False)

    status: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    direction: Mapped[Optional[str]] = mapped_column(String(4))
    rule_id: Mapped[Optional[int]] = mapped_column(ForeignKey("norm_rule.id"))
    rule_min: Mapped[Optional[float]] = mapped_column(Float)
    rule_max: Mapped[Optional[float]] = mapped_column(Float)
    rule_classification: Mapped[Optional[str]] = mapped_column(String(20))

    pool: Mapped[Pool] = relationship()
    parameter: Mapped[WaterParameter] = relationship()
    recorded_by: Mapped[AppUser] = relationship()


# Written once by services.measurements.create_measurement; never recomputed (see services/evaluation.py).
EVALUATION_COLUMNS = ("status", "direction", "rule_id", "rule_min", "rule_max", "rule_classification")


class EvaluationIsWriteOnce(ValueError):
    pass


@event.listens_for(Measurement, "before_update")
def _evaluation_is_write_once(_mapper, _connection, target: Measurement) -> None:
    """ORM guard: the create-time evaluation and rule snapshot of a measurement can never be changed by code."""
    state = inspect(target)
    changed = [column for column in EVALUATION_COLUMNS if state.attrs[column].history.has_changes()]
    if changed:
        raise EvaluationIsWriteOnce(f"measurement {target.id}: {', '.join(changed)} are set at creation only")
