"""Repository hygiene that broke before: the runner script and the npm lockfile."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parent.parent
RUNNER = APP_ROOT.parent / "for_testing"  # workspace/{for_testing,pool_records}: the only copy


def test_runner_lives_only_at_the_workspace_root():
    assert not (APP_ROOT / "for_testing").exists(), "pool_records/for_testing must not exist; use ../for_testing"


@pytest.mark.skipif(os.name == "nt" or not RUNNER.is_file(), reason="POSIX bits; runner only in the mount layout")
def test_runner_is_executable():
    assert os.access(RUNNER, os.X_OK), "chmod +x for_testing (and: git update-index --chmod=+x for_testing)"


def test_lockfile_matches_package_json():
    """``npm ci`` refuses a lockfile whose root entry disagrees with package.json."""
    package = json.loads((APP_ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((APP_ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
    root = lock["packages"][""]
    assert root.get("dependencies", {}) == package.get("dependencies", {})
    assert root.get("devDependencies", {}) == package.get("devDependencies", {})
    resolved = [entry["resolved"] for entry in lock["packages"].values() if "resolved" in entry]
    assert resolved and all(url.startswith("https://registry.npmjs.org/") for url in resolved)


def _resolve(packages: dict, from_path: str, name: str) -> bool:
    """Node resolution inside a lockfile: look in nested node_modules first, then walk up to the root."""
    base = from_path
    while True:
        if f"{base}/node_modules/{name}".lstrip("/") in packages:
            return True
        if not base:
            return False
        cut = base.rfind("/node_modules/")
        base = base[:cut] if cut != -1 else ""


def test_lockfile_is_complete_for_every_platform():
    """npm 11 ``npm ci`` refuses a lockfile that lacks any (optional) dependency, including native builds for
    other platforms (e.g. ``@rollup/rollup-darwin-arm64`` when the lock was generated on Linux)."""
    packages = json.loads((APP_ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8"))["packages"]
    missing = [
        f"{path or '<root>'} -> {name}"
        for path, entry in packages.items()
        for kind in ("dependencies", "optionalDependencies")
        for name in entry.get(kind, {})
        if not _resolve(packages, path, name)
    ]
    assert not missing, f"{len(missing)} missing, e.g. {missing[:3]}; regenerate the lock on a full registry"
    natives = [p for p in packages if p.startswith("node_modules/@rollup/rollup-")]
    assert any("darwin-arm64" in p for p in natives) and any("win32-x64" in p for p in natives)


def _runner(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(RUNNER), *args], capture_output=True, text=True, timeout=30)


@pytest.mark.skipif(not RUNNER.is_file() or shutil.which("bash") is None, reason="runner only in the mount layout")
def test_runner_options():
    """Default = no coverage; --cov enables the gate; anything else is a usage error (exit 2) before installing."""
    helped = _runner("--help")
    assert helped.returncode == 0
    assert "./for_testing --cov" in helped.stdout and "(no coverage)" in helped.stdout
    assert "--demo-data" in helped.stdout and "(end of usage)" not in helped.stdout
    for args in (("--no-cov",), ("--coverage",), ("cov",), ("--cov", "--demo", )):
        result = _runner(*args)
        assert result.returncode == 2 and f"unknown option '{args[-1]}'" in result.stderr
    text = RUNNER.read_text(encoding="utf-8")
    assert 'COVERAGE=""' in text and "--cov) COVERAGE=1" in text and "--demo-data) DEMO_DATA=1" in text
    assert "npm run test:cov" in text and "-m app.demo_data" in text
    assert "PORT=8001 ./for_testing" in helped.stdout and "./for_testing --e2e" in helped.stdout
    assert "--e2e) E2E=1" in text and "npx playwright test" in text and 'DATABASE_URL="$E2E_DB"' in text
    # never announce "running" without checking the port first and the served UI afterwards
    assert text.index('"$CHECK" port-free') < text.index("-m uvicorn app.main:app") < text.index('"$CHECK" spa')
    assert text.index('"$CHECK" spa') < text.index("AquaControl is running")
    assert 'FRONTEND_DIST="$DIST" exec' in text
