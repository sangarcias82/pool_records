

def test_health_is_public(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "AquaControl"}


def test_data_endpoints_require_a_session(client):
    for path in ("/api/auth/me", "/api/dashboard", "/api/clients", "/api/clients/1", "/api/pools", "/api/pools/1", "/api/parameters", "/api/norm-rules", "/api/measurements", "/api/measurements/1"):
        response = client.get(path)
        assert response.status_code == 401, path
        assert response.json() == {"detail": "Please sign in.", "key": "err.unauthenticated"}
    assert client.post("/api/clients", json={}).status_code == 401


def test_unknown_api_path_is_json_404(client):
    response = client.get("/api/nothing-here")
    assert response.status_code == 404
    assert response.json() == {"detail": "Unknown API endpoint.", "key": "err.unknown_endpoint"}


def test_dashboard_counts(admin):
    body = admin.get("/api/dashboard").json()
    assert body["counts"] == {"clients": 2, "pools": 2, "users": 3}
    assert body["measurements"] == {"today": 0, "out_of_range_last_7_days": 0}  # details: tests/test_dashboard.py




def test_translation_survives_bad_placeholders():
    from app.i18n import t

    assert t("es", "err.number") == "'{value}' no es un número válido."  # no params: untouched
    assert t("en", "err.number", other="x") == "'{value}' is not a valid number."  # missing param: raw text
    assert t("xx", "unknown.key") == "unknown.key"


def test_get_db_yields_a_working_session(db_session):
    from sqlalchemy import text

    from app.db import get_db

    generator = get_db()
    session = next(generator)
    assert session.execute(text("SELECT 1")).scalar() == 1
    generator.close()


def test_iso_utc_always_has_an_offset():
    from datetime import datetime, timedelta, timezone

    from app.utils import iso_utc, utc_now

    assert iso_utc(None) is None
    assert iso_utc(datetime(2025, 1, 2, 3, 4, 5)) == "2025-01-02T03:04:05+00:00"  # naive = UTC (SQLite)
    assert iso_utc(datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=-6)))) == "2025-01-02T09:04:05+00:00"
    assert utc_now().tzinfo is timezone.utc


def test_to_utc_naive_converts_instead_of_dropping_the_offset():
    from datetime import datetime, timedelta, timezone

    from app.utils import to_utc_naive

    assert to_utc_naive(datetime(2025, 6, 1, 8, 0, tzinfo=timezone(timedelta(hours=-6)))) == datetime(2025, 6, 1, 14, 0)
    assert to_utc_naive(datetime(2025, 6, 1, 8, 0)) == datetime(2025, 6, 1, 8, 0)  # naive is already UTC


def test_parse_id():
    from app.utils import parse_id

    assert [parse_id(v) for v in (3, "3", " 12 ")] == [3, 3, 12]
    assert [parse_id(v) for v in (None, 0, -1, True, 3.5, "x", "", "-2", "1.0")] == [None] * 9
