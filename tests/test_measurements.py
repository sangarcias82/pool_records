"""Measurements: POST/GET /api/measurements, folio MES-YYYYMMDD-####, validation (EN/ES), roles, scoping,
create-time evaluation with rule snapshot."""

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Client, Measurement, NormRule, Organization, Pool, WaterParameter
from app.services import measurements as measurement_service
from tests.helpers import ADMIN, SUPERVISOR, TECH

FIELDS = {
    "id", "folio", "pool_id", "pool_name", "client_id", "client_name", "parameter_id", "parameter_code",
    "parameter_name", "unit", "decimals", "value", "measured_at", "notes", "recorded_at", "recorded_by_id",
    "recorded_by_name", "status", "direction", "rule_id", "rule_min", "rule_max", "rule_classification",
}
FOLIO_RE = r"^MES-\d{8}-\d{4,}$"


@pytest.fixture()
def ids(db_session):
    """Seeded ids by name: pools and parameter codes."""
    pools = {p.name: p.id for p in db_session.scalars(select(Pool))}
    params = {p.code: p.id for p in db_session.scalars(select(WaterParameter))}
    return {"pool": pools["Semiolímpica"], "kids_pool": pools["Alberca infantil"], **params}


@pytest.fixture()
def capture(admin, ids):
    def _capture(code: str, value, expect: int = 201, api=None, **extra):
        body = {"pool_id": ids["pool"], "parameter_id": ids[code], "value": value, **extra}
        response = (api or admin).post("/api/measurements", json=body)
        assert response.status_code == expect, response.json()
        return response.json()

    return _capture


def _rule(db, code: str) -> NormRule:
    return db.scalar(select(NormRule).join(NormRule.parameter).where(WaterParameter.code == code))


def _row(db, measurement_id: int) -> Measurement:
    db.expire_all()
    return db.get(Measurement, measurement_id)


def _other_org(db):
    org = Organization(name="Other", slug="other")
    db.add(org)
    db.flush()
    client = Client(organization_id=org.id, name="Foreign client")
    db.add(client)
    db.flush()
    pool = Pool(organization_id=org.id, client_id=client.id, name="Foreign pool", volume_liters=100)
    db.add(pool)
    db.commit()
    return org, pool


def _at(text: str):
    """Fixed clock for folio tests."""
    return lambda: datetime.fromisoformat(text)


# --- Create: fields, roles, scoping ------------------------------------------------------------------------


def test_create_stores_every_field(capture, db_session, ids, user_by_email):
    body = capture("FREE_CHLORINE", "1,5", unit="mg/L", notes="  after backwash  ", measured_at="2025-06-01T08:30:00-06:00")
    assert set(body) == FIELDS
    row = _row(db_session, body["id"])
    admin_id = user_by_email(ADMIN).id
    assert (row.organization_id, row.pool_id, row.parameter_id) == (1, ids["pool"], ids["FREE_CHLORINE"])
    assert (row.value, row.unit, row.notes, row.recorded_by_id) == (1.5, "mg/L", "after backwash", admin_id)
    assert row.measured_at == datetime(2025, 6, 1, 14, 30)  # stored as UTC
    assert body["measured_at"] == "2025-06-01T14:30:00+00:00"
    assert (body["pool_name"], body["client_name"], body["parameter_code"]) == (
        "Semiolímpica", "Club Deportivo Las Palmas", "FREE_CHLORINE")
    assert (body["recorded_by_id"], body["recorded_by_name"]) == (admin_id, "Alicia Navarro")
    assert body["recorded_at"].endswith("+00:00")


@pytest.mark.parametrize("email", [ADMIN, SUPERVISOR, TECH])
def test_every_role_may_create(client, login_as, capture, email, user_by_email):
    login_as(email)
    body = capture("PH", 7.4, api=client)
    assert body["recorded_by_id"] == user_by_email(email).id


def test_capture_requires_a_session(client, ids):
    assert client.post("/api/measurements", json={"pool_id": ids["pool"]}).status_code == 401


def test_actor_must_belong_to_the_pools_organization(admin, db_session, ids):
    _, foreign_pool = _other_org(db_session)
    for pool_id in (foreign_pool.id, 9999):  # foreign looks exactly like missing: nothing is revealed
        response = admin.post("/api/measurements", json={"pool_id": pool_id, "parameter_id": ids["PH"], "value": 7})
        assert response.status_code == 404 and response.json()["key"] == "err.not_found"
    assert db_session.scalar(select(Measurement)) is None


@pytest.mark.parametrize("value", ["7,4", "7.4", 7.4, " 7,40 "])
def test_decimal_comma_and_dot(capture, value):
    assert capture("PH", value)["value"] == 7.4


def test_unit_is_copied_from_the_catalog_and_kept(capture, db_session):
    assert capture("PH", 7.4)["unit"] is None  # dimensionless
    assert capture("PH", 7.4, unit="")["unit"] is None
    first = capture("FREE_CHLORINE", 1.0, unit="MG/L")  # case-insensitive match
    assert first["unit"] == "mg/L"
    db_session.scalar(select(WaterParameter).where(WaterParameter.code == "FREE_CHLORINE")).unit = "ppm"
    db_session.commit()
    assert _row(db_session, first["id"]).unit == "mg/L"  # history keeps the unit it was read in
    assert capture("FREE_CHLORINE", 1.0)["unit"] == "ppm"


# --- Validation (EN/ES) ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "key"),
    [
        ({"pool_id": None}, "err.pool"),
        ({"pool_id": "abc"}, "err.pool"),
        ({"pool_id": 0}, "err.pool"),
        ({"pool_id": True}, "err.pool"),
        ({"parameter_id": None}, "err.parameter"),
        ({"parameter_id": 9999}, "err.parameter"),
        ({"parameter_id": "x"}, "err.parameter"),
        ({"value": None}, "err.value"),
        ({"value": "  "}, "err.value"),
        ({"value": "abc"}, "err.number"),
        ({"value": 15}, "err.rule_range"),  # physically impossible pH
        ({"unit": "ppm"}, "err.unit"),  # pH has no unit
        ({"unit": 5}, "err.unit"),
        ({"measured_at": "yesterday"}, "err.measured_at"),
        ({"measured_at": 20250601}, "err.measured_at"),  # a JSON number, not a string
        ({"measured_at": "20250601T083000"}, "err.measured_at"),  # compact form
        ({"measured_at": "2025-06-01"}, "err.measured_at"),  # time is required
        ({"measured_at": "2025-13-40T08:00"}, "err.measured_at"),  # right shape, impossible date
        ({"measured_at": "2999-01-01T00:00:00Z"}, "err.measured_future"),
    ],
)
def test_invalid_captures_are_rejected_and_nothing_is_saved(admin, ids, db_session, overrides, key):
    body = {"pool_id": ids["pool"], "parameter_id": ids["PH"], "value": 7.4} | overrides
    response = admin.post("/api/measurements", json=body)
    assert response.status_code == 422 and response.json()["key"] == key, response.json()
    assert db_session.scalar(select(Measurement)) is None


def test_future_measured_at_is_rejected_beyond_clock_drift(capture):
    now = datetime.now(timezone.utc)
    capture("PH", 7.4, measured_at=(now + timedelta(minutes=2)).isoformat())  # drift tolerated
    assert capture("PH", 7.4, expect=422, measured_at=(now + timedelta(minutes=10)).isoformat())["key"] == "err.measured_future"
    assert capture("PH", 7.4, expect=422, measured_at=(now + timedelta(days=1)).isoformat())["key"] == "err.measured_future"


@pytest.mark.parametrize(("sent", "stored"), [
    ("2025-06-01T14:00:00Z", "2025-06-01T14:00:00+00:00"),
    ("2025-06-01T14:00:00", "2025-06-01T14:00:00+00:00"),  # no offset = UTC
    ("2025-06-01T14:00:00.123Z", "2025-06-01T14:00:00.123000+00:00"),  # JavaScript toISOString()
    ("2025-06-01 08:00-06:00", "2025-06-01T14:00:00+00:00"),  # space separator, no seconds
])
def test_measured_at_formats(capture, sent, stored):
    assert capture("PH", 7.4, measured_at=sent)["measured_at"] == stored


def test_measured_at_defaults_to_now(capture):
    before = datetime.now(timezone.utc) - timedelta(seconds=1)
    for sent in (None, "  "):
        assert datetime.fromisoformat(capture("PH", 7.4, measured_at=sent)["measured_at"]) >= before


def test_inactive_parameter_cannot_be_captured(capture, db_session):
    db_session.scalar(select(WaterParameter).where(WaterParameter.code == "TDS")).active = False
    db_session.commit()
    assert capture("TDS", 100, expect=422)["key"] == "err.parameter"


@pytest.mark.parametrize(
    ("overrides", "es"),
    [
        ({"pool_id": None}, "Elige una alberca."),
        ({"parameter_id": None}, "Elige un parámetro de agua activo."),
        ({"value": None}, "Ingresa el valor medido."),
        ({"value": "x"}, "'x' no es un número válido."),
        ({"unit": "ppm"}, "La unidad 'ppm' no corresponde a este parámetro (se espera -)."),
        ({"measured_at": "2999-01-01T00:00:00Z"}, "La hora de la medición no puede estar en el futuro."),
    ],
)
def test_validation_errors_in_spanish(admin, ids, overrides, es):
    admin.post("/api/lang", json={"lang": "es"})
    body = {"pool_id": ids["pool"], "parameter_id": ids["PH"], "value": 7.4} | overrides
    assert admin.post("/api/measurements", json=body).json()["detail"] == es


def test_validation_errors_follow_accept_language_without_a_stored_choice(admin, ids):
    body = {"pool_id": ids["pool"], "parameter_id": ids["PH"], "value": None}
    assert admin.post("/api/measurements", json=body).json()["detail"] == "Enter the measured value."
    response = admin.post("/api/measurements", json=body, headers={"Accept-Language": "es-MX,es;q=0.9"})
    assert response.json()["detail"] == "Ingresa el valor medido."


# --- Folio MES-YYYYMMDD-#### -------------------------------------------------------------------------------


def test_folio_format_and_daily_sequence(capture):
    folios = [capture("PH", 7.4)["folio"] for _ in range(3)]
    today = datetime.now(timezone.utc).astimezone(ZoneInfo("America/Mexico_City")).strftime("%Y%m%d")
    assert folios == [f"MES-{today}-0001", f"MES-{today}-0002", f"MES-{today}-0003"]
    assert all(re.match(FOLIO_RE, f) for f in folios)


def _create(db, org_id, pool_id, parameter_id, user_id, when, **kw):
    data = {"pool_id": pool_id, "parameter_id": parameter_id, "value": 7.4, "measured_at": "2025-01-01T00:00:00Z"}
    return measurement_service.create_measurement(db, org_id, data, user_id, now=_at(when), **kw)


def test_counter_restarts_each_local_day_and_uses_the_org_time_zone(db_session, ids, user_by_email):
    uid = user_by_email(ADMIN).id
    args = (db_session, 1, ids["pool"], ids["PH"], uid)
    assert _create(*args, "2025-06-01T12:00:00+00:00").folio == "MES-20250601-0001"
    assert _create(*args, "2025-06-01T23:00:00+00:00").folio == "MES-20250601-0002"
    # 02:00 UTC on June 2nd is still June 1st (20:00) in Mexico City
    assert _create(*args, "2025-06-02T02:00:00+00:00").folio == "MES-20250601-0003"
    assert _create(*args, "2025-06-02T07:00:00+00:00").folio == "MES-20250602-0001"


def test_time_zone_setting_changes_the_folio_date(db_session, ids, user_by_email, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "timezone", "UTC")
    m = _create(db_session, 1, ids["pool"], ids["PH"], user_by_email(ADMIN).id, "2025-06-02T02:00:00+00:00")
    assert m.folio == "MES-20250602-0001"


def test_folio_is_unique_per_organization(db_session, ids, user_by_email):
    org, pool = _other_org(db_session)
    uid = user_by_email(ADMIN).id
    mine = _create(db_session, 1, ids["pool"], ids["PH"], uid, "2025-06-01T12:00:00+00:00")
    theirs = _create(db_session, org.id, pool.id, ids["PH"], uid, "2025-06-01T12:00:00+00:00")
    assert mine.folio == theirs.folio == "MES-20250601-0001"  # same folio, different organizations


def test_counter_grows_past_four_digits_instead_of_failing(db_session, ids, user_by_email):
    m = _create(db_session, 1, ids["pool"], ids["PH"], user_by_email(ADMIN).id, "2025-06-01T12:00:00+00:00",
                next_seq=lambda db, org, day: 10_000)
    assert m.folio == "MES-20250601-10000"


def test_folio_collision_is_retried(db_session, ids, user_by_email):
    uid = user_by_email(ADMIN).id
    _create(db_session, 1, ids["pool"], ids["PH"], uid, "2025-06-01T12:00:00+00:00")  # -0001 exists
    calls = []

    def stale_then_fresh(db, org_id, day):
        calls.append(day)
        return 1 if len(calls) == 1 else measurement_service._next_seq(db, org_id, day)

    m = _create(db_session, 1, ids["pool"], ids["PH"], uid, "2025-06-01T13:00:00+00:00", next_seq=stale_then_fresh)
    assert m.folio == "MES-20250601-0002" and calls == ["20250601", "20250601"]


def test_folio_collision_gives_up_after_three_attempts(db_session, ids, user_by_email):
    uid = user_by_email(ADMIN).id
    _create(db_session, 1, ids["pool"], ids["PH"], uid, "2025-06-01T12:00:00+00:00")
    with pytest.raises(IntegrityError):
        _create(db_session, 1, ids["pool"], ids["PH"], uid, "2025-06-01T13:00:00+00:00", next_seq=lambda db, org, day: 1)
    assert len(db_session.scalars(select(Measurement)).all()) == 1


# --- List + filters ----------------------------------------------------------------------------------------


def test_list_is_newest_first_and_filters_combine(admin, capture, ids):
    old = capture("PH", 7.4, measured_at="2025-01-01T10:00:00Z")
    low = capture("PH", 6.5, measured_at="2025-01-02T10:00:00Z")
    chlorine = capture("FREE_CHLORINE", 2.0, measured_at="2025-01-03T10:00:00Z")
    no_rule = capture("TOTAL_CHLORINE", 2.0, measured_at="2025-01-04T10:00:00Z")
    kids = admin.post("/api/measurements", json={"pool_id": ids["kids_pool"], "parameter_id": ids["PH"], "value": 7.5}).json()

    def listed(**params):
        response = admin.get("/api/measurements", params=params)
        assert response.status_code == 200
        return [m["id"] for m in response.json()]

    assert listed() == [kids["id"], no_rule["id"], chlorine["id"], low["id"], old["id"]]
    assert listed(pool_id=ids["kids_pool"]) == [kids["id"]]
    assert listed(parameter_id=ids["PH"]) == [kids["id"], low["id"], old["id"]]
    assert listed(status="out_of_range") == [low["id"]]
    assert listed(status="NO_RULE") == [no_rule["id"]]
    assert listed(status="OK", parameter_id=ids["PH"], pool_id=ids["pool"]) == [old["id"]]
    assert listed(status="") == listed()  # empty status = unset
    assert listed(limit=2) == [kids["id"], no_rule["id"]]
    assert len(listed(limit=0)) == 1 and len(listed(limit=10_000)) == 5  # clamped to 1..200
    assert admin.get(f"/api/measurements/{old['id']}").json() == old


def test_bad_filters_are_translated_422(admin):
    response = admin.get("/api/measurements", params={"status": "BAD"})
    assert response.status_code == 422 and response.json()["key"] == "err.status_filter"
    response = admin.get("/api/measurements", params={"pool_id": "abc"})
    assert response.status_code == 422 and response.json()["key"] == "err.required"


def test_every_role_can_list_and_reads_are_scoped(client, login_as, capture, db_session, ids, user_by_email):
    org, pool = _other_org(db_session)
    foreign = _create(db_session, org.id, pool.id, ids["PH"], user_by_email(ADMIN).id, "2025-06-01T12:00:00+00:00")
    mine = capture("PH", 7.4)
    for email in (ADMIN, SUPERVISOR, TECH):
        login_as(email)
        assert [m["id"] for m in client.get("/api/measurements").json()] == [mine["id"]]
        assert client.get(f"/api/measurements/{foreign.id}").status_code == 404
        client.post("/api/auth/logout")
    login_as(TECH)
    assert client.get("/api/measurements", params={"pool_id": pool.id}).json() == []
    assert client.get("/api/measurements/9999").status_code == 404


# --- Evaluation at create time (kept from the previous step) -------------------------------------------------


def _persisted(db, body):
    row = _row(db, body["id"])
    return row.status, row.direction, row.rule_id, row.rule_min, row.rule_max


def test_inside_bounds_is_ok(capture, db_session):
    body = capture("PH", 7.4)
    ph_rule = _rule(db_session, "PH").id
    assert (body["status"], body["direction"], body["rule_id"], body["rule_min"], body["rule_max"]) == (
        "OK", None, ph_rule, 7.2, 7.8)
    assert _persisted(db_session, body) == ("OK", None, ph_rule, 7.2, 7.8)


def test_below_min_is_out_of_range_low(capture, db_session):
    body = capture("PH", "6,9")
    ph_rule = _rule(db_session, "PH").id
    assert (body["status"], body["direction"]) == ("OUT_OF_RANGE", "LOW")
    assert _persisted(db_session, body) == ("OUT_OF_RANGE", "LOW", ph_rule, 7.2, 7.8)


def test_above_max_is_out_of_range_high(capture, db_session):
    body = capture("PH", 8.1)
    ph_rule = _rule(db_session, "PH").id
    assert (body["status"], body["direction"]) == ("OUT_OF_RANGE", "HIGH")
    assert _persisted(db_session, body) == ("OUT_OF_RANGE", "HIGH", ph_rule, 7.2, 7.8)


def test_bounds_are_inclusive_end_to_end(capture):
    assert [capture("PH", v)["status"] for v in (7.2, 7.8)] == ["OK", "OK"]


def test_inactive_or_missing_rule_is_no_rule(capture, db_session):
    body = capture("TOTAL_CHLORINE", 9.0)  # rule seeded inactive
    assert (body["status"], body["direction"], body["rule_id"], body["rule_min"]) == ("NO_RULE", None, None, None)
    assert _persisted(db_session, body) == ("NO_RULE", None, None, None, None)
    db_session.delete(_rule(db_session, "PH"))
    db_session.commit()
    assert capture("PH", 7.4)["status"] == "NO_RULE"


def test_rules_of_other_organizations_are_never_used(capture, db_session):
    org, _ = _other_org(db_session)
    ph = _rule(db_session, "PH")
    db_session.add(NormRule(organization_id=org.id, parameter_id=ph.parameter_id, min_value=0, max_value=1))
    db_session.delete(ph)
    db_session.commit()
    assert capture("PH", 7.4)["status"] == "NO_RULE"


def test_editing_the_rule_does_not_rewrite_past_measurements(admin, capture, db_session):
    ok, high = capture("PH", 7.4), capture("PH", 7.9)
    ph = _rule(db_session, "PH")
    response = admin.patch(f"/api/norm-rules/{ph.id}", json={"min_value": 7.5, "max_value": 8.0, "classification": "COMPLEMENTARY"})
    assert response.status_code == 200
    for before in (ok, high):
        assert admin.get(f"/api/measurements/{before['id']}").json() == before
        row = _row(db_session, before["id"])
        assert (row.rule_min, row.rule_max, row.rule_classification) == (7.2, 7.8, "NORMATIVE")
    assert (ok["status"], high["direction"]) == ("OK", "HIGH")
    assert capture("PH", 7.4)["direction"] == "LOW"  # new captures use the edited rule
    assert capture("PH", 7.9)["status"] == "OK"
    admin.patch(f"/api/norm-rules/{ph.id}", json={"active": False})
    assert admin.get(f"/api/measurements/{ok['id']}").json() == ok
    assert capture("PH", 7.4)["status"] == "NO_RULE"


def test_evaluation_runs_only_when_a_measurement_is_created(admin, capture, db_session, monkeypatch):
    calls = []
    real = measurement_service.evaluate

    def spy(value, rule):
        calls.append(value)
        return real(value, rule)

    monkeypatch.setattr(measurement_service, "evaluate", spy)
    created = capture("PH", 7.4)
    assert calls == [7.4]
    admin.get("/api/measurements")
    admin.get(f"/api/measurements/{created['id']}")
    admin.get("/api/measurements", params={"status": "OK"})
    admin.patch(f"/api/norm-rules/{_rule(db_session, 'PH').id}", json={"min_value": 7.5})
    assert calls == [7.4]  # reads and rule edits never evaluate


def test_rule_patch_sends_no_write_to_the_measurement_table(admin, capture, db_session):
    from sqlalchemy import event

    capture("PH", 7.4)
    statements = []

    def record(_conn, _cursor, statement, *_args):
        statements.append(statement.upper())

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", record)
    try:
        rule_id = _rule(db_session, "PH").id
        for body in ({"min_value": 7.5, "max_value": 8.0}, {"classification": "COMPLEMENTARY"}, {"active": False}):
            assert admin.patch(f"/api/norm-rules/{rule_id}", json=body).status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", record)
    assert any(sql.startswith("UPDATE NORM_RULE") for sql in statements)  # the listener did see the rule writes
    writes = [sql for sql in statements if sql.startswith(("UPDATE", "INSERT", "DELETE")) and "MEASUREMENT" in sql]
    assert writes == []


def test_evaluation_columns_are_write_once(capture, db_session):
    from app.models import EVALUATION_COLUMNS, EvaluationIsWriteOnce

    row = _row(db_session, capture("PH", 6.9)["id"])
    for column, value in zip(EVALUATION_COLUMNS, ("OK", None, None, 0.0, 14.0, "COMPLEMENTARY")):
        setattr(row, column, value)
        with pytest.raises(EvaluationIsWriteOnce, match=column):
            db_session.commit()
        db_session.rollback()
    row = _row(db_session, row.id)
    assert (row.status, row.direction, row.rule_min, row.rule_max) == ("OUT_OF_RANGE", "LOW", 7.2, 7.8)
    row.notes = "other columns stay editable by code"
    db_session.commit()
    assert _row(db_session, row.id).notes == "other columns stay editable by code"


# --- Database constraints --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "MAYBE", "direction": None},
        {"status": "OUT_OF_RANGE", "direction": None},
        {"status": "OK", "direction": "LOW"},
        {"status": "OK", "direction": None, "rule_id": None},
        {"status": "NO_RULE", "direction": None},
        {"folio_seq": 1, "folio": "MES-20250601-0009"},  # duplicate day + counter
        {"folio_seq": 9, "folio": "MES-20250601-0001"},  # duplicate folio
    ],
)
def test_database_rejects_inconsistent_rows(db_session, ids, user_by_email, overrides):
    existing = _create(db_session, 1, ids["pool"], ids["PH"], user_by_email(ADMIN).id, "2025-06-01T12:00:00+00:00")
    columns = ("organization_id", "pool_id", "parameter_id", "value", "unit", "measured_at", "recorded_at",
               "recorded_by_id", "folio_date", "rule_id", "rule_min", "rule_max", "rule_classification")
    values = {c: getattr(existing, c) for c in columns} | {
        "folio_seq": 2, "folio": "MES-20250601-0002", "status": "OK", "direction": None} | overrides
    db_session.add(Measurement(**values))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
