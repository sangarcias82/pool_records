"""FastAPI serves the built SPA; without a build it explains how to create one."""

from fastapi.testclient import TestClient

from app.main import create_app


def _dist(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id='root'>spa</div>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('hi')", encoding="utf-8")
    return dist


def test_missing_build_returns_clear_message(client, tmp_path):
    response = client.get("/clients")
    detail = response.json()["detail"]
    assert response.status_code == 503 and "npm run build" in detail
    assert str(tmp_path / "no-dist" / "index.html") in detail  # which copy of the project answered
    assert client.get("/api/health").status_code == 200


def test_startup_logs_where_the_ui_comes_from(db_session, tmp_path, caplog):
    with caplog.at_level("INFO", logger="uvicorn.error"):
        create_app(frontend_dist=tmp_path / "missing")
        create_app(frontend_dist=_dist(tmp_path))
    assert "Web UI not built" in caplog.text and "Serving the web UI from" in caplog.text


def test_build_made_while_running_is_picked_up(db_session, tmp_path):
    dist = tmp_path / "later"
    with TestClient(create_app(frontend_dist=dist)) as spa:
        assert spa.get("/").status_code == 503
        dist.mkdir()
        (dist / "index.html").write_text("<div id='root'></div>", encoding="utf-8")
        assert spa.get("/").status_code == 200


def test_built_spa_is_served_with_history_fallback(db_session, tmp_path):
    with TestClient(create_app(frontend_dist=_dist(tmp_path))) as spa:
        for path in ("/", "/clients", "/pools/3"):
            assert "id='root'" in spa.get(path).text, path
        assert spa.get("/assets/app.js").text == "console.log('hi')"
        assert spa.get("/api/nope").status_code == 404


def test_root_level_files_are_served_but_not_outside_dist(db_session, tmp_path):
    dist = _dist(tmp_path)
    (dist / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("nope", encoding="utf-8")
    with TestClient(create_app(frontend_dist=dist)) as spa:
        assert spa.get("/favicon.svg").text == "<svg/>"
        assert "id='root'" in spa.get("/..%2Fsecret.txt").text  # traversal falls back to index.html


def test_placeholder_secret_key_is_logged(monkeypatch, caplog, tmp_path):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "secret_key", "YOUR_SECRET_KEY_HERE")
    with caplog.at_level("WARNING"):
        create_app(frontend_dist=tmp_path)
    assert "SECRET_KEY is the placeholder value" in caplog.text
