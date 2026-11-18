#!/usr/bin/env bash
# Build a mount zip: workspace/{pool_records,for_testing}
# Output: ../pool_records_mount.zip (next to the project folder). No .git, venv, local DB or .env.
set -euo pipefail
APP_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="$(cd "$APP_ROOT/.." && pwd)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$STAGE/pool_records"
rsync -a \
  --exclude '.git' \
  --exclude 'venv' \
  --exclude 'node_modules' \
  --exclude 'frontend/dist' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude '*.db' \
  --exclude '.env' \
  --exclude 'tests/test_aquacontrol.db' \
  --exclude '.DS_Store' \
  "$APP_ROOT/" "$STAGE/pool_records/"


# for_testing sits at the mount root and also inside the project (clone convenience)
cp "$APP_ROOT/for_testing" "$STAGE/for_testing"
chmod +x "$STAGE/for_testing" "$STAGE/pool_records/for_testing" "$STAGE/pool_records/scripts/pack_archive.sh"

ZIP="$OUT_DIR/pool_records_mount.zip"
rm -f "$ZIP"
(cd "$STAGE" && zip -r -X "$ZIP" pool_records for_testing \
  -x '*/.git/*' '*/venv/*' '*/.venv/*' '*/node_modules/*' \
  -x '*__pycache__*' '*/.pytest_cache/*' '*.db' '*/.env' '*.pyc' '*/.DS_Store')

echo "Wrote $ZIP"
if unzip -l "$ZIP" | grep -q '\.git/'; then echo "FAIL: .git present"; exit 1; fi
echo "OK: no .git"
if unzip -l "$ZIP" | grep -qE '(venv/|\.env$|\.db$)'; then echo "FAIL: venv, .env or .db present"; exit 1; fi
echo "OK: no venv, .env or .db"
unzip -l "$ZIP" | grep -qE ' for_testing$' || { echo "FAIL: for_testing missing at mount root"; exit 1; }
echo "OK: for_testing present"
ls -lh "$ZIP"
