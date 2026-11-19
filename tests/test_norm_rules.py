"""Norm rules: per-organization ranges, planning-default seed, GET for everyone, PATCH for ORG_ADMIN only."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db import Base
from app.models import CLASSIFICATIONS, NormRule, Organization, WaterParameter
from app.seed import DEFAULT_NORM_RULES, PARAMETER_CATALOG, ensure_default_rules, run_seed
from tests.helpers import ADMIN, SUPERVISOR, TECH

FIELDS = {
    "id", "parameter_id", "parameter_code", "parameter_name", "unit", "decimals", "min_value", "max_value",
    "classification", "source_notes", "active", "updated_at", "updated_by_name",
}


def _rules(api) -> dict[str, dict]:
    return {r["parameter_code"]: r for r in api.get("/api/norm-rules").json()}


def _patch(api, code: str, body: dict):
    return api.patch(f"/api/norm-rules/{_rules(api)[code]['id']}", json=body)


def _count(db) -> int:
    return db.scalar(select(func.count()).select_from(NormRule))


@pytest.fixture()
def foreign_rule(db_session):
    other = Organization(name="Other", slug="other")
    db_session.add(other)
    db_session.flush()
    ph_id = db_session.scalar(select(WaterParameter.id).where(WaterParameter.code == "PH"))
    rule = NormRule(organization_id=other.id, parameter_id=ph_id, min_value=6.0, max_value=9.0)
    db_session.add(rule)
    db_session.commit()
    return rule


# --- GET -------------------------------------------------------------------------------------------------


def test_endpoints_require_a_session(client):
    assert client.get("/api/norm-rules").status_code == 401
    assert client.patch("/api/norm-rules/1", json={"active": False}).status_code == 401


@pytest.mark.parametrize("email", [ADMIN, SUPERVISOR, TECH])
def test_every_role_can_read_the_rules(client, login_as, email):
    login_as(email)
    response = client.get("/api/norm-rules")
    assert response.status_code == 200
    assert [r["parameter_code"] for r in response.json()] == [spec.code for spec in PARAMETER_CATALOG]


def test_rows_carry_rule_and_parameter_display_fields(admin):
    rules = _rules(admin)
    assert all(set(r) == FIELDS for r in rules.values())
    ph = rules["PH"]
    assert (ph["min_value"], ph["max_value"], ph["classification"], ph["active"]) == (7.2, 7.8, "NORMATIVE", True)
    assert (ph["parameter_name"], ph["unit"], ph["decimals"]) == ("pH", None, 1)
    assert ph["updated_at"] is None and ph["updated_by_name"] is None  # untouched planning default
    assert rules["COMBINED_CHLORINE"]["min_value"] is None and rules["COMBINED_CHLORINE"]["max_value"] == 0.2
    assert rules["TOTAL_ALKALINITY"]["classification"] == "COMPLEMENTARY"
    assert {code for code, r in rules.items() if not r["active"]} == {"TOTAL_CHLORINE", "TDS"}
    assert all(r["source_notes"].startswith("Valor de planeación") for r in rules.values())


def test_list_is_scoped_to_the_organization(admin, foreign_rule):
    rules = admin.get("/api/norm-rules").json()
    assert foreign_rule.id not in {r["id"] for r in rules} and len(rules) == len(DEFAULT_NORM_RULES)


# --- PATCH: happy paths -----------------------------------------------------------------------------------


def test_admin_updates_bounds_and_the_edit_is_stamped(admin):
    before = datetime.now(timezone.utc)
    response = _patch(admin, "PH", {"min_value": "7,0", "max_value": 7.6})
    assert response.status_code == 200
    body = response.json()
    assert (body["min_value"], body["max_value"]) == (7.0, 7.6)
    assert body["updated_by_name"] == "Alicia Navarro"
    assert datetime.fromisoformat(body["updated_at"]) >= before.replace(microsecond=0)
    assert body["updated_at"].endswith("+00:00")
    assert _rules(admin)["PH"] == body  # persisted


def test_partial_patch_only_touches_the_given_fields(admin):
    body = _patch(admin, "TDS", {"active": True}).json()
    assert body["active"] is True and body["max_value"] == 1500 and body["classification"] == "COMPLEMENTARY"
    body = _patch(admin, "TDS", {"classification": " normative "}).json()
    assert body["classification"] == "NORMATIVE" and body["active"] is True


def test_null_or_blank_clears_one_bound(admin):
    assert _patch(admin, "PH", {"min_value": None}).json()["min_value"] is None
    assert _patch(admin, "FREE_CHLORINE", {"max_value": ""}).json()["max_value"] is None


def test_equal_bounds_are_allowed(admin):
    body = _patch(admin, "TEMPERATURE", {"min_value": 28, "max_value": 28}).json()
    assert (body["min_value"], body["max_value"]) == (28, 28)


def test_parameter_without_physical_max_accepts_large_limits(admin):
    assert _patch(admin, "TDS", {"max_value": 6000}).json()["max_value"] == 6000


def test_no_op_patch_does_not_stamp_an_edit(admin):
    rules = _rules(admin)
    for body in ({}, {"min_value": 7.2, "active": True}):
        response = admin.patch(f"/api/norm-rules/{rules['PH']['id']}", json=body)
        assert response.status_code == 200 and response.json()["updated_at"] is None


# --- PATCH: validation ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "body", "key"),
    [
        ("PH", {"min_value": 8, "max_value": 7}, "err.rule_order"),
        ("PH", {"min_value": 7.9}, "err.rule_order"),  # merged with stored max 7.8
        ("PH", {"min_value": None, "max_value": None}, "err.rule_bounds"),
        ("COMBINED_CHLORINE", {"max_value": None}, "err.rule_bounds"),  # min already empty
        ("PH", {"max_value": 15}, "err.rule_range"),
        ("PH", {"min_value": -1}, "err.rule_range"),
        ("PH", {"min_value": "abc"}, "err.number"),
        ("PH", {"classification": "LEGAL"}, "err.rule_classification"),
        ("PH", {"classification": None}, "err.rule_classification"),
        ("PH", {"classification": 3}, "err.rule_classification"),
        ("PH", {"active": "yes"}, "err.rule_active"),
        ("PH", {"active": None}, "err.rule_active"),
        ("PH", {"source_notes": "mine"}, "err.rule_field"),
        ("PH", {"parameter_id": 2, "min_value": 7}, "err.rule_field"),
    ],
)
def test_invalid_patches_are_rejected_and_change_nothing(admin, code, body, key):
    before = _rules(admin)[code]
    response = _patch(admin, code, body)
    assert response.status_code == 422 and response.json()["key"] == key, response.json()
    assert _rules(admin)[code] == before


def test_validation_messages_are_translated(admin):
    admin.post("/api/lang", json={"lang": "es"})
    response = _patch(admin, "PH", {"max_value": 15})
    assert response.json()["detail"] == "15 está fuera del rango posible de pH."
    response = _patch(admin, "PH", {"min_value": 8, "max_value": 7})
    assert response.json()["detail"] == "El mínimo debe ser menor o igual que el máximo."


def test_body_must_be_a_json_object(admin):
    rule_id = _rules(admin)["PH"]["id"]
    response = admin.patch(f"/api/norm-rules/{rule_id}", json=[1, 2])
    assert response.status_code == 422 and response.json()["key"] == "err.required"


# --- PATCH: permissions and scoping -----------------------------------------------------------------------


@pytest.mark.parametrize("email", [SUPERVISOR, TECH])
def test_only_org_admin_can_patch(client, login_as, email):
    login_as(email)
    response = _patch(client, "PH", {"min_value": 7.0})
    assert response.status_code == 403 and response.json()["key"] == "forbidden"
    assert _rules(client)["PH"]["min_value"] == 7.2


def test_capability_flags(client, login_as):
    for email, expected in ((ADMIN, True), (SUPERVISOR, False), (TECH, False)):
        assert login_as(email)["can"]["manage_norm_rules"] is expected


def test_missing_and_foreign_rules_are_404(admin, foreign_rule):
    assert admin.patch("/api/norm-rules/9999", json={"active": False}).status_code == 404
    response = admin.patch(f"/api/norm-rules/{foreign_rule.id}", json={"min_value": 1})
    assert response.status_code == 404 and response.json()["key"] == "err.not_found"


# --- Seed ------------------------------------------------------------------------------------------------


def test_default_rules_are_consistent_with_the_catalog():
    catalog = {spec.code: spec for spec in PARAMETER_CATALOG}
    assert [spec.code for spec in DEFAULT_NORM_RULES] == list(catalog)  # one default per parameter
    for rule in DEFAULT_NORM_RULES:
        parameter = catalog[rule.code]
        assert rule.classification in CLASSIFICATIONS
        assert rule.min_value is not None or rule.max_value is not None
        for bound in (rule.min_value, rule.max_value):
            if bound is not None:
                assert parameter.physical_min <= bound
                assert parameter.physical_max is None or bound <= parameter.physical_max
        if rule.min_value is not None and rule.max_value is not None:
            assert rule.min_value <= rule.max_value
        assert rule.source_notes.startswith("Valor de planeación")


def test_seed_is_idempotent_and_keeps_admin_edits(admin, db_session):
    _patch(admin, "PH", {"min_value": 6.8})
    assert ensure_default_rules(db_session) == 0
    run_seed(db_session)
    assert _count(db_session) == len(DEFAULT_NORM_RULES)
    assert _rules(admin)["PH"]["min_value"] == 6.8


def test_seed_restores_only_missing_rules(db_session):
    db_session.delete(db_session.scalar(select(NormRule).join(NormRule.parameter).where(WaterParameter.code == "TDS")))
    db_session.commit()
    assert ensure_default_rules(db_session) == 1
    assert _count(db_session) == len(DEFAULT_NORM_RULES)


def test_seed_skips_defaults_for_parameters_missing_from_the_catalog(db_session):
    tds = db_session.scalar(select(WaterParameter).where(WaterParameter.code == "TDS"))
    db_session.delete(db_session.scalar(select(NormRule).where(NormRule.parameter_id == tds.id)))
    db_session.delete(tds)
    db_session.commit()
    assert ensure_default_rules(db_session) == 0


def test_seed_without_demo_organization_adds_nothing(db_session):
    db_session.scalar(select(Organization)).slug = "renamed"
    db_session.commit()
    db_session.execute(NormRule.__table__.delete())
    db_session.commit()
    assert ensure_default_rules(db_session) == 0 and _count(db_session) == 0


def test_database_from_previous_version_gets_default_rules(db_session):
    """A DB created before this feature (no norm_rule table) receives the defaults on the next start."""
    bind = db_session.get_bind()
    db_session.close()
    NormRule.__table__.drop(bind)
    Base.metadata.create_all(bind=bind)
    run_seed(db_session)
    assert _count(db_session) == len(DEFAULT_NORM_RULES)


# --- Database constraints --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"parameter_code": "PH"},  # duplicate (organization, parameter)
        {"min_value": 5, "max_value": 1},
        {"min_value": None, "max_value": None},
        {"classification": "LEGAL"},
    ],
)
def test_database_rejects_invalid_rules(db_session, overrides):
    code = overrides.pop("parameter_code", None)
    if code is None:  # a parameter without a rule, so only the overridden value can fail
        db_session.add(WaterParameter(code="ORP", name="ORP"))
        db_session.flush()
        code = "ORP"
    parameter_id = db_session.scalar(select(WaterParameter.id).where(WaterParameter.code == code))
    values = {"organization_id": 1, "parameter_id": parameter_id, "min_value": 1.0, "max_value": 2.0} | overrides
    db_session.add(NormRule(**values))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_rule_defaults(db_session):
    db_session.add(WaterParameter(code="ORP", name="ORP"))
    db_session.flush()
    orp_id = db_session.scalar(select(WaterParameter.id).where(WaterParameter.code == "ORP"))
    rule = NormRule(organization_id=1, parameter_id=orp_id, min_value=650)
    db_session.add(rule)
    db_session.commit()
    assert (rule.classification, rule.active, rule.source_notes, rule.updated_at) == ("NORMATIVE", True, None, None)
