from app.i18n import EN, ES


def test_health_is_public(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "AquaControl"}


def test_data_endpoints_require_a_session(client):
    for path in ("/api/auth/me", "/api/dashboard", "/api/clients", "/api/clients/1", "/api/pools", "/api/pools/1"):
        response = client.get(path)
        assert response.status_code == 401, path
        assert response.json()["detail"] == "Not authenticated"
    assert client.post("/api/clients", json={}).status_code == 401


def test_unknown_api_path_is_json_404(client):
    response = client.get("/api/nothing-here")
    assert response.status_code == 404 and response.json() == {"detail": "Unknown API endpoint"}


def test_dashboard_counts(admin):
    assert admin.get("/api/dashboard").json() == {"counts": {"clients": 2, "pools": 2, "users": 3}}


def test_error_dictionaries_are_in_sync():
    assert set(EN) == set(ES)
