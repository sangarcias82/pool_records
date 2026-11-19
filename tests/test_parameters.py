"""Water parameter catalog: API, seeding (R1) and database constraints."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.auth import hash_password
from app.db import Base
from app.models import AppUser, Client, NormRule, Organization, UserCredential, WaterParameter
from app.seed import PARAMETER_CATALOG, ensure_demo_data, ensure_parameters, run_seed
from tests.helpers import ADMIN, PASSWORD, SUPERVISOR, TECH

EXPECTED_CODES = [
    "PH",
    "FREE_CHLORINE",
    "TOTAL_CHLORINE",
    "COMBINED_CHLORINE",
    "CYANURIC_ACID",
    "TURBIDITY",
    "TOTAL_ALKALINITY",
    "CALCIUM_HARDNESS",
    "TEMPERATURE",
    "TDS",
]
FIELDS = {"id", "code", "name", "unit", "decimals", "physical_min", "physical_max", "sort_order", "active"}


def _count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


# --- API -------------------------------------------------------------------------------------------------


def test_requires_a_session(client):
    response = client.get("/api/parameters")
    assert response.status_code == 401 and response.json()["key"] == "err.unauthenticated"


@pytest.mark.parametrize("email", [ADMIN, SUPERVISOR, TECH])
def test_every_role_can_read_the_catalog(client, login_as, email):
    login_as(email)
    response = client.get("/api/parameters")
    assert response.status_code == 200
    assert [p["code"] for p in response.json()] == EXPECTED_CODES


def test_rows_are_thin_and_carry_the_catalog_values(admin):
    rows = {p["code"]: p for p in admin.get("/api/parameters").json()}
    assert all(set(row) == FIELDS for row in rows.values())
    assert rows["PH"] | {"id": 0} == {
        "id": 0, "code": "PH", "name": "pH", "unit": None, "decimals": 1,
        "physical_min": 0, "physical_max": 14, "sort_order": 10, "active": True,
    }
    assert rows["FREE_CHLORINE"]["unit"] == "mg/L" and rows["FREE_CHLORINE"]["decimals"] == 2
    assert rows["TURBIDITY"]["unit"] == "NTU"
    assert rows["TEMPERATURE"]["unit"] == "°C"
    assert rows["TDS"]["physical_min"] == 0 and rows["TDS"]["physical_max"] is None  # optional bound
    sort_orders = [p["sort_order"] for p in rows.values()]
    assert sort_orders == sorted(sort_orders)


def test_inactive_parameters_are_hidden_unless_requested(admin, db_session):
    db_session.scalar(select(WaterParameter).where(WaterParameter.code == "TURBIDITY")).active = False
    db_session.commit()

    default = [p["code"] for p in admin.get("/api/parameters").json()]
    assert "TURBIDITY" not in default and len(default) == 9

    everything = admin.get("/api/parameters", params={"include_inactive": "true"}).json()
    assert [p["code"] for p in everything] == EXPECTED_CODES
    assert next(p for p in everything if p["code"] == "TURBIDITY")["active"] is False


def test_sort_order_ties_fall_back_to_code(admin, db_session):
    for code in ("TDS", "PH"):
        db_session.scalar(select(WaterParameter).where(WaterParameter.code == code)).sort_order = 1
    db_session.commit()
    assert [p["code"] for p in admin.get("/api/parameters").json()][:2] == ["PH", "TDS"]


def test_bad_include_inactive_value_is_a_translated_422(admin):
    response = admin.get("/api/parameters", params={"include_inactive": "maybe"})
    assert response.status_code == 422 and response.json()["key"] == "err.required"


def test_catalog_is_global_across_organizations(client, login_as, db_session):
    other = Organization(name="Otra Org", slug="otra")
    db_session.add(other)
    db_session.flush()
    user = AppUser(organization_id=other.id, email="ana@otra.example", full_name="Ana", role="TECHNICIAN")
    user.credential = UserCredential(password_hash=hash_password(PASSWORD, iterations=1000))
    db_session.add(user)
    db_session.commit()

    login_as("ana@otra.example")
    assert [p["code"] for p in client.get("/api/parameters").json()] == EXPECTED_CODES


# --- Seeding (R1) ----------------------------------------------------------------------------------------


def test_catalog_definition_is_consistent():
    codes = [spec.code for spec in PARAMETER_CATALOG]
    assert codes == EXPECTED_CODES and len(set(codes)) == len(codes)
    assert len({spec.sort_order for spec in PARAMETER_CATALOG}) == len(codes)
    for spec in PARAMETER_CATALOG:
        assert spec.code == spec.code.upper() and " " not in spec.code
        assert 0 <= spec.decimals <= 4
        if spec.physical_min is not None and spec.physical_max is not None:
            assert spec.physical_min <= spec.physical_max


def test_seed_is_idempotent(db_session):
    assert _count(db_session, WaterParameter) == len(PARAMETER_CATALOG)
    assert ensure_demo_data(db_session) is False
    assert ensure_parameters(db_session) == 0
    run_seed(db_session)
    assert _count(db_session, WaterParameter) == len(PARAMETER_CATALOG)
    assert _count(db_session, Organization) == 1 and _count(db_session, Client) == 2


def test_existing_database_without_catalog_gets_it_on_next_start(db_session):
    """A DB created before this feature: the org exists, the water_parameter table does not."""
    bind = db_session.get_bind()
    db_session.close()
    NormRule.__table__.drop(bind)  # references water_parameter, so it goes first
    WaterParameter.__table__.drop(bind)

    Base.metadata.create_all(bind=bind)  # what init_db does on startup
    run_seed(db_session)

    assert _count(db_session, WaterParameter) == len(PARAMETER_CATALOG)
    assert _count(db_session, Organization) == 1 and _count(db_session, Client) == 2  # demo data not duplicated


def test_seed_adds_only_missing_codes_and_keeps_local_edits(db_session):
    ph = db_session.scalar(select(WaterParameter).where(WaterParameter.code == "PH"))
    ph.name, ph.active = "pH (edited)", False
    tds = db_session.scalar(select(WaterParameter).where(WaterParameter.code == "TDS"))
    db_session.delete(db_session.scalar(select(NormRule).where(NormRule.parameter_id == tds.id)))
    db_session.delete(tds)
    db_session.commit()

    assert ensure_parameters(db_session) == 1  # only TDS comes back
    db_session.refresh(ph)
    assert ph.name == "pH (edited)" and ph.active is False


# --- Database constraints --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"code": "PH"},  # duplicate code
        {"decimals": 5},
        {"decimals": -1},
        {"physical_min": 10, "physical_max": 1},
    ],
)
def test_database_rejects_invalid_parameters(db_session, overrides):
    values = {"code": "NEW_ONE", "name": "New", "unit": None, "decimals": 1, "sort_order": 999} | overrides
    db_session.add(WaterParameter(**values))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_defaults_apply_to_minimal_rows(db_session):
    row = WaterParameter(code="ORP", name="Oxidation-reduction potential")
    db_session.add(row)
    db_session.commit()
    assert (row.decimals, row.sort_order, row.active, row.unit, row.physical_min) == (1, 0, True, None, None)
