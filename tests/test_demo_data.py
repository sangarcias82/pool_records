"""Demo measurement loader: realistic, deterministic, idempotent, built through the real services."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app.demo_data import INCIDENTS, JACUZZI_NOTE, OLD_PH_BOUNDS, load_demo_measurements, main
from app.models import Measurement, NormRule, Organization, Pool, WaterParameter

NOON_MEXICO = datetime(2025, 6, 15, 18, 0, tzinfo=timezone.utc)  # 12:00 in America/Mexico_City


def _load(db, **kw):
    return load_demo_measurements(db, now=lambda: NOON_MEXICO, **kw)


def _rows(db, code=None):
    stmt = select(Measurement).join(Measurement.parameter).order_by(Measurement.measured_at, Measurement.id)
    if code:
        stmt = stmt.where(WaterParameter.code == code)
    return db.scalars(stmt).all()


def _ph_rule(db):
    return db.scalar(select(NormRule).join(NormRule.parameter).where(WaterParameter.code == "PH"))


def test_loads_every_status_and_detail(db_session):
    summary = _load(db_session)
    rows = _rows(db_session)
    assert summary.created == len(rows) > 200 and summary.rule_change is True
    assert set(summary.by_status) == {"OK", "OUT_OF_RANGE", "NO_RULE"}
    assert {r.direction for r in rows} == {None, "LOW", "HIGH"}
    assert {r.recorded_by.role for r in rows} == {"ORG_ADMIN", "SUPERVISOR", "TECHNICIAN"}
    assert {r.pool.name for r in rows} == {"Semiolímpica", "Alberca infantil", "Jacuzzi"}
    assert len({r.folio_date for r in rows}) == 15  # 14 days back + today
    assert summary.folios[0] == "MES-20250601-0001" and summary.folios[-1].startswith("MES-20250615-")
    assert all(r.measured_at <= NOON_MEXICO.replace(tzinfo=None) for r in rows)  # nothing in the future
    assert {r.parameter.code for r in rows if r.status == "NO_RULE"} == {"TOTAL_CHLORINE", "TDS"}  # inactive rules
    assert sum(1 for r in rows if r.notes) >= len(INCIDENTS)


def test_every_incident_is_flagged_with_its_note(db_session):
    _load(db_session)
    for (_days_ago, pool, code), (value, notes) in INCIDENTS.items():
        row = db_session.scalar(select(Measurement).where(Measurement.notes == notes["es"]))  # Spanish by default
        assert (row.pool.name, row.parameter.code, row.value, row.status) == (pool, code, value, "OUT_OF_RANGE"), note


def test_rule_change_mid_history_is_visible_in_snapshots(db_session):
    before = (_ph_rule(db_session).min_value, _ph_rule(db_session).max_value)
    _load(db_session)
    snapshots = [(r.rule_min, r.rule_max) for r in _rows(db_session, "PH")]
    assert snapshots[0] == OLD_PH_BOUNDS and snapshots[-1] == before == (7.2, 7.8)
    assert snapshots == sorted(snapshots)  # one switch, old -> current, never back
    changed = db_session.scalar(select(Measurement).where(Measurement.notes.like("Correcto con la regla de hoy%")))
    assert (changed.value, changed.direction, changed.rule_max) == (7.7, "HIGH", 7.6)  # OK under today's rule
    rule = _ph_rule(db_session)
    assert (rule.min_value, rule.max_value, rule.active) == (7.2, 7.8, True)  # restored
    assert rule.updated_by.role == "ORG_ADMIN"


def test_admin_edited_ph_rule_is_restored_to_the_edited_bounds(db_session):
    rule = _ph_rule(db_session)
    rule.min_value, rule.max_value = 6.8, 8.0
    db_session.commit()
    _load(db_session)
    rule = _ph_rule(db_session)
    assert (rule.min_value, rule.max_value) == (6.8, 8.0)
    assert _rows(db_session, "PH")[-1].rule_max == 8.0


def test_short_history_still_restores_the_rule(db_session):
    summary = _load(db_session, days=3)  # never reaches the change day
    assert summary.rule_change and len({r.folio_date for r in _rows(db_session)}) == 4
    assert {(r.rule_min, r.rule_max) for r in _rows(db_session, "PH")} == {OLD_PH_BOUNDS}
    assert (_ph_rule(db_session).min_value, _ph_rule(db_session).max_value) == (7.2, 7.8)


def test_inactive_ph_rule_means_no_change_and_no_rule_rows(db_session):
    _ph_rule(db_session).active = False
    db_session.commit()
    summary = _load(db_session, days=3)
    assert summary.rule_change is False and "no (PH rule inactive)" in "\n".join(summary.lines())
    assert {r.status for r in _rows(db_session, "PH")} == {"NO_RULE"}


def test_is_deterministic_and_refuses_to_run_twice(db_session):
    first = _load(db_session, days=3)
    values = [(r.folio, r.value, r.status) for r in _rows(db_session)]
    second = _load(db_session, days=3)
    assert second.created == 0 and "already has" in second.skipped
    assert second.lines() == [f"Demo measurements not loaded: the demo organization already has {first.created} measurements"]
    assert [(r.folio, r.value, r.status) for r in _rows(db_session)] == values
    assert db_session.scalar(select(func.count()).select_from(Pool).where(Pool.name == "Jacuzzi")) == 1


def test_same_seed_gives_the_same_history(db_session):
    _load(db_session, days=3)
    first = [(r.folio, r.value) for r in _rows(db_session)]
    db_session.execute(Measurement.__table__.delete())
    db_session.commit()
    _load(db_session, days=3)
    assert [(r.folio, r.value) for r in _rows(db_session)] == first


def test_without_the_demo_organization_nothing_happens(db_session):
    db_session.scalar(select(Organization)).slug = "renamed"
    db_session.commit()
    assert _load(db_session).skipped == "the demo organization does not exist"


def test_command_line_entry_point(db_session, capsys):
    assert main(["--days", "2"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("Demo measurements loaded: ") and "Folios MES-" in out
    assert main([]) == 0
    assert "not loaded: the demo organization already has" in capsys.readouterr().out


@pytest.mark.parametrize("email", ["admin@aquacontrol.example", "tech@aquacontrol.example"])
def test_loaded_rows_are_served_by_the_api(client, login_as, db_session, email):
    _load(db_session, days=2)
    login_as(email)
    rows = client.get("/api/measurements", params={"limit": 200}).json()
    assert len(rows) == len(_rows(db_session)) and {r["status"] for r in rows} >= {"OK", "NO_RULE"}
    assert client.get("/api/measurements", params={"status": "NO_RULE"}).json()[0]["rule_id"] is None


def test_notes_are_spanish_by_default_and_english_on_request(db_session):
    """Notes are stored free text: the demo organization is Mexican, so Spanish unless asked otherwise."""
    _load(db_session, days=1)
    notes = {r.notes for r in _rows(db_session) if r.notes}
    assert notes == {JACUZZI_NOTE["es"], INCIDENTS[(1, "Semiolímpica", "CYANURIC_ACID")][1]["es"]}
    db_session.execute(Measurement.__table__.delete())
    db_session.commit()
    _load(db_session, days=1, lang="en")
    assert JACUZZI_NOTE["en"] in {r.notes for r in _rows(db_session)}


def test_every_incident_has_both_languages_and_unknown_lang_is_refused(db_session):
    assert all(set(notes) == {"es", "en"} for _value, notes in INCIDENTS.values()) and set(JACUZZI_NOTE) == {"es", "en"}
    with pytest.raises(ValueError, match="lang must be one of"):
        load_demo_measurements(db_session, lang="fr")


def test_command_line_language_option(db_session, capsys):
    assert main(["--days", "1", "--lang", "en"]) == 0
    assert JACUZZI_NOTE["en"] in {r.notes for r in _rows(db_session)}
