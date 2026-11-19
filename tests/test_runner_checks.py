"""scripts/runner_checks.py: what ../for_testing uses to make sure the browser gets THIS build."""

import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import runner_checks  # noqa: E402


def _serve(routes: dict[str, tuple[int, str]]):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            status, body = routes.get(self.path, (404, "nope"))
            self.send_response(status)
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


@pytest.fixture()
def old_server():
    """An AquaControl whose SPA is not built (the situation seen on the Mac)."""
    server, base = _serve({
        "/api/health": (200, '{"status": "ok", "app": "AquaControl"}'),
        "/": (503, '{"detail": "The web UI is not built yet. Run: cd frontend && npm install && npm run build"}'),
    })
    yield server, base
    server.shutdown()


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_port_free_and_who(old_server):
    server, _ = old_server
    busy = server.server_address[1]
    assert runner_checks.port_free(busy) is False
    assert "another AquaControl server is already running" in runner_checks.who(busy)
    free = _free_port()
    assert runner_checks.port_free(free) and runner_checks.who(free) == f"nothing listens on port {free}"


def test_other_programs_are_named_as_such():
    server, _ = _serve({"/api/health": (200, '{"hello": "world"}')})
    try:
        assert runner_checks.who(server.server_address[1]).startswith("another program is listening")
    finally:
        server.shutdown()


def test_health_requires_aquacontrol(old_server):
    _, base = old_server
    assert runner_checks.health_ok(base)
    server, other = _serve({"/api/health": (200, "not json")})
    try:
        assert not runner_checks.health_ok(other)
    finally:
        server.shutdown()
    assert not runner_checks.health_ok(f"http://127.0.0.1:{_free_port()}")


def test_spa_status_explains_what_the_browser_would_get(old_server):
    _, base = old_server
    ok, message = runner_checks.spa_status(base)
    assert not ok and "HTTP 503" in message and "not built" in message
    server, good = _serve({"/": (200, '<!doctype html><div id="root"></div>')})
    try:
        assert runner_checks.spa_status(good) == (True, "ok")
    finally:
        server.shutdown()
    ok, message = runner_checks.spa_status(f"http://127.0.0.1:{_free_port()}")
    assert not ok and "failed" in message


def test_command_line(old_server, capsys):
    server, base = old_server
    port = str(server.server_address[1])
    assert runner_checks.main(["port-free", port]) == 1
    assert runner_checks.main(["port-free", str(_free_port())]) == 0
    assert runner_checks.main(["who", port]) == 0 and "AquaControl" in capsys.readouterr().out
    assert runner_checks.main(["health", base]) == 0
    assert runner_checks.main(["spa", base]) == 1 and "HTTP 503" in capsys.readouterr().out
    assert runner_checks.main(["bogus", "x"]) == 2
