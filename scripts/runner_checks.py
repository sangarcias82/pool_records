"""Checks used by ../for_testing around starting the server. Standard library only.

    python scripts/runner_checks.py port-free PORT      exit 0 if nothing listens on 127.0.0.1:PORT
    python scripts/runner_checks.py who PORT            describe what listens there (stdout)
    python scripts/runner_checks.py health BASE_URL     exit 0 if BASE_URL/api/health answers as AquaControl
    python scripts/runner_checks.py spa BASE_URL        exit 0 if BASE_URL/ serves the built SPA (else the reason)

Why: if another server (an earlier run, another copy of the project) already holds the port, the new server cannot
bind, but a plain health check is answered by the old one and the browser shows the old one's pages.
"""

from __future__ import annotations

import json
import socket
import sys
import urllib.error
import urllib.request
from typing import Optional

SPA_MARKER = 'id="root"'  # frontend/index.html -> dist/index.html


def port_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) != 0


def _get(url: str, timeout: float = 2.0) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def _health(base: str) -> Optional[dict]:
    try:
        status, body = _get(f"{base}/api/health", timeout=1.0)
        data = json.loads(body)
    except (OSError, ValueError):
        return None
    return data if status == 200 and isinstance(data, dict) else None


def health_ok(base: str) -> bool:
    data = _health(base)
    return bool(data and data.get("app") == "AquaControl")


def who(port: int) -> str:
    if port_free(port):
        return f"nothing listens on port {port}"
    if health_ok(f"http://127.0.0.1:{port}"):
        return (f"another AquaControl server is already running on port {port} (an earlier ./for_testing or uvicorn, "
                "maybe from another copy of the project); the browser would get ITS pages, not this build")
    return f"another program is listening on port {port}"


def spa_status(base: str) -> tuple[bool, str]:
    try:
        status, body = _get(f"{base}/")
    except OSError as exc:
        return False, f"GET {base}/ failed: {exc}"
    if status == 200 and SPA_MARKER in body:
        return True, "ok"
    return False, f"GET {base}/ -> HTTP {status}: {body.strip()[:300]}"


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in {"port-free", "who", "health", "spa"}:
        print(__doc__, file=sys.stderr)
        return 2
    command, arg = argv
    if command == "port-free":
        return 0 if port_free(int(arg)) else 1
    if command == "who":
        print(who(int(arg)))
        return 0
    if command == "health":
        return 0 if health_ok(arg) else 1
    ok, message = spa_status(arg)
    if not ok:
        print(message)
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
