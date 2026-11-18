"""FastAPI serves the built SPA; without a build it explains how to create one."""

from fastapi.testclient import TestClient

from app.main import create_app


def _dist(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id='root'>spa</div>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('hi')", encoding="utf-8")
    return dist


def test_missing_build_returns_clear_message(client):
    response = client.get("/clients")
    assert response.status_code == 503 and "npm run build" in response.json()["detail"]
    assert client.get("/api/health").status_code == 200


def test_built_spa_is_served_with_history_fallback(db_session, tmp_path):
    with TestClient(create_app(frontend_dist=_dist(tmp_path))) as spa:
        for path in ("/", "/clients", "/pools/3"):
            assert "id='root'" in spa.get(path).text, path
        assert spa.get("/assets/app.js").text == "console.log('hi')"
        assert spa.get("/api/nope").status_code == 404
