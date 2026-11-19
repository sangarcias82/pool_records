"""Fake but realistic measurements for the demo organization, for trying the measurement pages.

Everything goes through the real services (``create_measurement``, ``update_rule``, ``create_pool``), so folios,
create-time evaluation and rule snapshots are exactly what a user would get. Deterministic (fixed random seed).

    venv/bin/python -m app.demo_data [--lang es|en]   # or: ../for_testing --demo-data

What it creates (about two weeks ending now, in ``Settings.timezone``):

- morning visits to every pool, an afternoon visit to the big outdoor pool, a weekly lab panel;
- OK rows, OUT_OF_RANGE LOW/HIGH incidents with notes, NO_RULE rows (parameters whose rule is inactive);
- a "Jacuzzi" pool whose 37 °C water is HIGH against the pool temperature rule;
- a PH rule change in the middle: older rows keep the old rule snapshot (7.0 - 7.6), newer ones the current rule;
  the rule is restored to the bounds it had before the load.

It refuses to run when the demo organization already has measurements (delete ``aquacontrol.db`` to start over).
"""

from __future__ import annotations

import argparse
import random
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AppUser, Client, Measurement, NormRule, Organization, Pool, WaterParameter
from app.seed import DEMO_ORG_SLUG, run_seed
from app.services import measurements as measurement_service
from app.services import norm_rules as rule_service
from app.services import pools as pool_service
from app.utils import utc_now

DEMO_DAYS = 14
RANDOM_SEED = 20250601
EXTRA_POOL = {"client": "Hotel Brisa Marina", "name": "Jacuzzi", "volume_liters": 2500, "environment": "INDOOR"}
OLD_PH_BOUNDS = (7.0, 7.6)  # PH rule in force for the older half of the history
RULE_CHANGE_DAYS_AGO = 7  # from this day on, the PH rule has its current bounds again
RECORDING_DELAY = timedelta(minutes=10)  # a visit is typed in a few minutes after the sample

# (center, spread) of a well-kept pool; values are clamped to center +- 2 spreads.
TYPICAL: dict[str, tuple[float, float]] = {
    "PH": (7.45, 0.12),
    "FREE_CHLORINE": (1.8, 0.35),
    "TOTAL_CHLORINE": (2.0, 0.35),
    "COMBINED_CHLORINE": (0.1, 0.04),
    "CYANURIC_ACID": (35, 6),
    "TURBIDITY": (0.25, 0.08),
    "TOTAL_ALKALINITY": (100, 8),
    "CALCIUM_HARDNESS": (290, 30),
    "TEMPERATURE": (27.5, 0.8),
    "TDS": (900, 120),
}
JACUZZI_TEMPERATURE = (37.5, 0.4)
# Notes are free text typed by users, stored and shown as typed (the UI does not translate data). The demo
# organization is Mexican, so its notes are Spanish like its client and pool names; ``--lang en`` writes English.
NOTE_LANGS = ("es", "en")
JACUZZI_NOTE = {
    "es": "El agua del spa se mantiene a 37-38 °C; la regla de temperatura de la organización es para albercas",
    "en": "Spa water is kept at 37-38 °C; the organization's temperature rule is written for pools",
}

# Deliberate incidents: (days ago, pool, parameter) -> (value, note).
INCIDENTS: dict[tuple[int, str, str], tuple[float, dict[str, str]]] = {
    (12, "Semiolímpica", "PH"): (7.7, {
        "es": "Correcto con la regla de hoy (7.2 - 7.8) pero arriba del límite de 7.6 vigente entonces",
        "en": "Fine for today's rule (7.2 - 7.8) but above the 7.6 limit in force then"}),
    (10, "Alberca infantil", "FREE_CHLORINE"): (0.6, {
        "es": "Uso intenso durante una fiesta infantil", "en": "Heavy use during a birthday party"}),
    (9, "Semiolímpica", "PH"): (6.9, {
        "es": "Sobredosis de ácido; corregido con carbonato de sodio", "en": "Acid overdose; corrected with sodium carbonate"}),
    (5, "Semiolímpica", "FREE_CHLORINE"): (4.8, {
        "es": "Tratamiento de choque la noche anterior", "en": "Shock treatment the night before"}),
    (4, "Alberca infantil", "COMBINED_CHLORINE"): (0.5, {
        "es": "Padres reportan fuerte olor a cloro", "en": "Strong chlorine smell reported by parents"}),
    (3, "Semiolímpica", "TURBIDITY"): (0.9, {
        "es": "Retrolavado del filtro atrasado", "en": "Filter backwash overdue"}),
    (2, "Alberca infantil", "PH"): (8.1, {
        "es": "Reposición de agua nueva, pH aún sin ajustar", "en": "Fresh water top-up, pH not yet adjusted"}),
    (1, "Semiolímpica", "CYANURIC_ACID"): (62, {
        "es": "Demasiadas pastillas de cloro estabilizado", "en": "Too many stabilized chlorine tablets"}),
}


@dataclass
class DemoSummary:
    created: int = 0
    skipped: Optional[str] = None
    by_status: Counter = field(default_factory=Counter)
    folios: list[str] = field(default_factory=list)
    rule_change: bool = False

    def lines(self) -> list[str]:
        if self.skipped:
            return [f"Demo measurements not loaded: {self.skipped}"]
        statuses = ", ".join(f"{status} {count}" for status, count in sorted(self.by_status.items()))
        return [
            f"Demo measurements loaded: {self.created} ({statuses})",
            f"Folios {self.folios[0]} ... {self.folios[-1]}",
            "PH rule snapshot change mid-history: " + ("yes (7.0 - 7.6 -> current)" if self.rule_change else "no (PH rule inactive)"),
        ]


def _visits(pools: dict[str, Pool], days: int) -> list[tuple[int, time, Pool]]:
    """(days ago, local time, pool) in the order they happen, oldest first (so folios follow the clock)."""
    visits = []
    for days_ago in range(days, -1, -1):
        for name, pool in pools.items():
            visits.append((days_ago, time(9, 0), pool))
            if name == "Semiolímpica":
                visits.append((days_ago, time(17, 30), pool))
    return sorted(visits, key=lambda v: (-v[0], v[1]))


def _parameters_for(days_ago: int, pool: Pool, at: time) -> list[str]:
    codes = ["PH", "FREE_CHLORINE", "TEMPERATURE"]
    if days_ago % 2 == 0:
        codes += ["TOTAL_CHLORINE", "COMBINED_CHLORINE"]
    if days_ago % 3 == 1 and pool.environment == "OUTDOOR":
        codes.append("CYANURIC_ACID")
    if days_ago % 7 == 3 and at.hour < 12:  # weekly lab panel
        codes += ["TOTAL_ALKALINITY", "CALCIUM_HARDNESS", "TURBIDITY", "TDS"]
    incidents = [code for (ago, name, code) in INCIDENTS if ago == days_ago and name == pool.name and at.hour < 12]
    return codes + [code for code in incidents if code not in codes]


def _value(rng: random.Random, code: str, pool: Pool, parameter: WaterParameter) -> float:
    center, spread = JACUZZI_TEMPERATURE if (pool.name == EXTRA_POOL["name"] and code == "TEMPERATURE") else TYPICAL[code]
    value = min(max(rng.gauss(center, spread), center - 2 * spread), center + 2 * spread)
    return round(max(value, 0.0), parameter.decimals)


def _ensure_extra_pool(db: Session, org_id: int) -> Pool:
    existing = db.scalar(select(Pool).where(Pool.organization_id == org_id, Pool.name == EXTRA_POOL["name"]))
    if existing:
        return existing
    client = db.scalar(select(Client).where(Client.organization_id == org_id, Client.name == EXTRA_POOL["client"]))
    data = {k: EXTRA_POOL[k] for k in ("name", "volume_liters", "environment")}
    return pool_service.create_pool(db, org_id, client.id, data)


def load_demo_measurements(
    db: Session, *, days: int = DEMO_DAYS, now: Optional[Callable[[], datetime]] = None, lang: str = "es"
) -> DemoSummary:
    """Create the demo history for the demo organization. Returns what was created (or why nothing was).

    ``lang`` is the language of the notes (free text, stored as typed): ``es`` (default) or ``en``.
    """
    if lang not in NOTE_LANGS:
        raise ValueError(f"lang must be one of {NOTE_LANGS}")
    org = db.scalar(select(Organization).where(Organization.slug == DEMO_ORG_SLUG))
    if org is None:
        return DemoSummary(skipped="the demo organization does not exist")
    existing = db.scalar(select(func.count()).select_from(Measurement).where(Measurement.organization_id == org.id))
    if existing:
        return DemoSummary(skipped=f"the demo organization already has {existing} measurements")

    users = {u.role: u for u in db.scalars(select(AppUser).where(AppUser.organization_id == org.id))}
    parameters = {p.code: p for p in db.scalars(select(WaterParameter).where(WaterParameter.active.is_(True)))}
    _ensure_extra_pool(db, org.id)
    pools = {p.name: p for p in db.scalars(select(Pool).where(Pool.organization_id == org.id).order_by(Pool.id))}

    zone = ZoneInfo(get_settings().timezone)
    current = (now or utc_now)().astimezone(timezone.utc)
    today = current.astimezone(zone).date()
    rng = random.Random(RANDOM_SEED)
    summary = DemoSummary()

    ph_rule = db.scalar(
        select(NormRule).where(NormRule.organization_id == org.id, NormRule.parameter_id == parameters["PH"].id)
    )
    restore = None
    if ph_rule is not None and ph_rule.active:
        restore = {"min_value": ph_rule.min_value, "max_value": ph_rule.max_value}
        old = {"min_value": OLD_PH_BOUNDS[0], "max_value": OLD_PH_BOUNDS[1]}
        rule_service.update_rule(db, org.id, ph_rule.id, old, users["ORG_ADMIN"].id)
        summary.rule_change = True

    for days_ago, at, pool in _visits(pools, days):
        if restore is not None and days_ago == RULE_CHANGE_DAYS_AGO:
            rule_service.update_rule(db, org.id, ph_rule.id, restore, users["ORG_ADMIN"].id)
            restore = None
        measured = datetime.combine(today - timedelta(days=days_ago), at, tzinfo=zone).astimezone(timezone.utc)
        if measured + RECORDING_DELAY > current:
            continue  # later today: not visited yet
        recorder = users["SUPERVISOR"] if at.hour >= 12 else users["ORG_ADMIN"] if days_ago % 5 == 0 else users["TECHNICIAN"]
        for code in _parameters_for(days_ago, pool, at):
            incident = INCIDENTS.get((days_ago, pool.name, code)) if at.hour < 12 else None
            value = incident[0] if incident else _value(rng, code, pool, parameters[code])
            note = incident[1][lang] if incident else None
            if pool.name == EXTRA_POOL["name"] and code == "TEMPERATURE":
                note = JACUZZI_NOTE[lang]
            typed = str(value).replace(".", ",") if len(summary.folios) % 3 == 0 else value  # some typed with a comma
            data = {"pool_id": pool.id, "parameter_id": parameters[code].id, "value": typed,
                    "measured_at": measured.isoformat(), "notes": note}
            created = measurement_service.create_measurement(
                db, org.id, data, recorder.id, now=lambda m=measured: m + RECORDING_DELAY
            )
            summary.created += 1
            summary.by_status[created.status] += 1
            summary.folios.append(created.folio)
    if restore is not None:  # history shorter than the rule change point
        rule_service.update_rule(db, org.id, ph_rule.id, restore, users["ORG_ADMIN"].id)
    return summary


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.demo_data", description=__doc__.split("\n\n")[0])
    parser.add_argument("--days", type=int, default=DEMO_DAYS, help=f"days of history (default {DEMO_DAYS})")
    parser.add_argument("--lang", choices=NOTE_LANGS, default="es", help="language of the notes (default es)")
    args = parser.parse_args(argv)

    from app import db as db_module  # current engine (tests rebind it)

    db_module.upgrade_schema(db_module.engine)
    with db_module.SessionLocal() as db:
        run_seed(db)
        summary = load_demo_measurements(db, days=args.days, lang=args.lang)
    print("\n".join(summary.lines()))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
