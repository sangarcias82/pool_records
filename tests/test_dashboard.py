"""GET /api/dashboard measurement widgets: windows in the organization's time zone, matching list filters."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models import Client, Organization, Pool, WaterParameter
from app.services import dashboard as dashboard_service
from app.services import measurements as measurement_service
from tests.helpers import ADMIN, SUPERVISOR, TECH

# 2025-06-15 12:00 in Mexico City (UTC-6): today starts 2025-06-15T06:00Z, the 7-day window 2025-06-09T06:00Z.
NOW = datetime(2025, 6, 15, 18, 0, tzinfo=timezone.utc)


@pytest.fixture()
def capture(db_session, user_by_email):
    pool_id = db_session.scalar(select(Pool.id).where(Pool.name == "Semiolímpica"))
    ph = db_session.scalar(select(WaterParameter.id).where(WaterParameter.code == "PH"))
    uid = user_by_email(ADMIN).id

    def _capture(measured_at: str, value: float, org_id: int = 1, pool: int = pool_id):
        data = {"pool_id": pool, "parameter_id": ph, "value": value, "measured_at": measured_at}
        return measurement_service.create_measurement(db_session, org_id, data, uid, now=lambda: NOW)

    return _capture


def test_windows_are_local_calendar_days():
    w = dashboard_service.windows(NOW, "America/Mexico_City")
    assert w["today_from"].isoformat() == "2025-06-15T00:00:00-06:00"
    assert w["last_7_days_from"].isoformat() == "2025-06-09T00:00:00-06:00"
    # 03:00Z on the 16th is still the 15th in Mexico City: same local day
    late = dashboard_service.windows(datetime(2025, 6, 16, 3, 0, tzinfo=timezone.utc), "America/Mexico_City")
    assert late["today_from"] == w["today_from"]
    assert dashboard_service.windows(NOW, "UTC")["today_from"].isoformat() == "2025-06-15T00:00:00+00:00"


def test_counts_today_and_out_of_range_last_7_days(db_session, capture):
    capture("2025-06-15T07:00:00Z", 7.4)  # today 01:00 local, OK
    capture("2025-06-15T17:00:00Z", 8.3)  # today, HIGH
    capture("2025-06-15T05:59:00Z", 6.5)  # 23:59 local on the 14th: not today, but within 7 days, LOW
    capture("2025-06-09T06:00:00Z", 8.5)  # local midnight six days ago: first instant of the window, HIGH
    capture("2025-06-09T05:59:59Z", 8.5)  # one second earlier: outside the window
    capture("2025-06-01T12:00:00Z", 9.0)  # two weeks ago, HIGH, outside
    body = dashboard_service.dashboard(db_session, 1, now=lambda: NOW)
    assert body["measurements"] == {"today": 2, "out_of_range_last_7_days": 3}
    assert body["windows"] == {
        "timezone": "America/Mexico_City",
        "today_from": "2025-06-15T06:00:00Z",
        "last_7_days_from": "2025-06-09T06:00:00Z",
    }


def test_other_organizations_are_not_counted(db_session, capture):
    org = Organization(name="Other", slug="other")
    db_session.add(org)
    db_session.flush()
    client = Client(organization_id=org.id, name="C")
    db_session.add(client)
    db_session.flush()
    pool = Pool(organization_id=org.id, client_id=client.id, name="P", volume_liters=10)
    db_session.add(pool)
    db_session.commit()
    capture("2025-06-15T17:00:00Z", 8.3, org_id=org.id, pool=pool.id)
    assert dashboard_service.dashboard(db_session, 1, now=lambda: NOW)["measurements"] == {
        "today": 0, "out_of_range_last_7_days": 0}
    assert dashboard_service.dashboard(db_session, org.id, now=lambda: NOW)["measurements"]["today"] == 1


@pytest.mark.parametrize("email", [ADMIN, SUPERVISOR, TECH])
def test_widgets_match_the_lists_they_link_to(client, login_as, email):
    """Every role sees the widgets; following the window start gives exactly the counted rows."""
    login_as(email)
    for value, when in ((7.4, None), (8.5, None), (6.0, "2025-01-01T10:00:00Z")):  # two now, one long ago
        body = {"pool_id": 1, "parameter_id": 1, "value": value, **({"measured_at": when} if when else {})}
        assert client.post("/api/measurements", json=body).status_code == 201
    dash = client.get("/api/dashboard").json()
    assert dash["measurements"] == {"today": 2, "out_of_range_last_7_days": 1}
    today = client.get("/api/measurements", params={"measured_from": dash["windows"]["today_from"]}).json()
    week_out = client.get("/api/measurements", params={
        "measured_from": dash["windows"]["last_7_days_from"], "status": "OUT_OF_RANGE"}).json()
    assert len(today) == 2 and len(week_out) == 1 and week_out[0]["value"] == 8.5
    assert len(client.get("/api/measurements", params={"status": "OUT_OF_RANGE"}).json()) == 2  # incl. the old one


def test_measured_from_filter_validation(admin):
    for bad in ("yesterday", "2025-06-01", "2025-13-40T00:00"):
        response = admin.get("/api/measurements", params={"measured_from": bad})
        assert response.status_code == 422 and response.json()["key"] == "err.measured_at", bad
    assert admin.get("/api/measurements", params={"measured_from": ""}).json() == []  # empty = no filter, no rows yet
    ok = admin.get("/api/measurements", params={"measured_from": "2025-06-01T00:00:00-06:00"})
    assert ok.status_code == 200


def test_dashboard_requires_a_session(client):
    assert client.get("/api/dashboard").status_code == 401
