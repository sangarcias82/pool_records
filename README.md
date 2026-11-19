# AquaControl (light base)

A small starting point for pool-service management: a FastAPI JSON API and a Vite + React + TypeScript SPA.
It contains auth, one organization, clients, pools, the water parameter catalog, per-organization norm rules and
measurements evaluated against those rules at capture time. Product features are built later (see below).

Contents: [Stack](#stack) · [Quick start](#quick-start) · [Demo logins](#demo-logins-dummy-credentials-password-aquademo1) ·
[What exists](#what-exists) · [Conventions](#conventions-for-new-features) · [Configuration](#configuration) ·
[Water parameter catalog](#water-parameter-catalog) · [Norm rules](#norm-rules-per-organization) ·
[Measurements](#measurements) · [SPA: measurement pages](#spa-measurement-pages) · [Demo measurements](#demo-measurements) ·
[SPA: norm rules page](#spa-norm-rules-page) · [Dashboard widgets](#dashboard-widgets) ·
[Error responses](#error-responses) · [Internationalization](#internationalization-enes) · [Testing](#testing) ·
[Robustness and known limits](#robustness-and-known-limits) · [Manual verification](#manual-verification-besides-pytest) ·
[Troubleshooting](#troubleshooting) · [Out of scope](#out-of-scope--later-work)

## Stack

- Backend: FastAPI, SQLAlchemy 2, SQLite, session cookie auth (PBKDF2 hashes in `user_credential`)
- Frontend: Vite, React 18, TypeScript, react-router, EN/ES dictionaries (no UI framework, one CSS file)
- Tests: `pytest` (API, auth, org scoping, seeding, schema upgrade, demo data, dashboard, SPA serving, repo hygiene)
  and `vitest` (i18n key parity, `src/lib` evaluation/formatting/labels/rule edits). The test database runs with
  `PRAGMA synchronous=OFF` (tests only, it is thrown away). With `--cov` both have a 90% gate: pytest on `app/`
  (`.coveragerc`), vitest on `src/lib` (`vite.config.ts`)
- Browser end-to-end tests with Playwright (`./for_testing --e2e`), see [Testing](#testing)
- Tested on Python 3.10 to 3.14, Node 22 and 25, npm 10 and 11
- FastAPI serves `frontend/dist` and falls back to `index.html` for non-`/api` paths. No server-rendered pages.

## Quick start

Requirements: Python 3.10+, Node.js 18+ (22 LTS recommended) unless `SKIP_FRONTEND=1`, bash (the macOS system
bash 3.2 is fine), internet access for pip/npm on the first run.

The runner `for_testing` lives at the **workspace root, next to this folder** (`workspace/{for_testing,pool_records/}`);
there is no copy inside `pool_records/`. Run it from the workspace root:

```bash
cd ..                         # workspace root (the folder that contains pool_records/)
./for_testing                 # install deps, build the SPA, vitest + pytest (no coverage), serve :8000
./for_testing --cov           # same, with pytest + vitest coverage reports and 90% gates (exit 1 below)
./for_testing --demo-data     # also load ~270 fake measurements before serving (see "Demo measurements")
./for_testing --cov --demo-data
./for_testing --e2e           # also run the browser tests on a throwaway server + database (see "Testing")
./for_testing --cov --demo-data --e2e   # everything
./for_testing --help
SKIP_FRONTEND=1 ./for_testing # API only, no Node needed
PYTHON=/path/to/python ./for_testing   # use an interpreter that already has requirements.txt installed
PORT=8001 ./for_testing       # serve on another port (default 8000)

# or by hand, inside pool_records/
python3 -m venv venv && venv/bin/pip install -r requirements.txt
(cd frontend && npm install && npm run build)
cp .env.example .env          # set SECRET_KEY
venv/bin/uvicorn app.main:app --reload     # http://127.0.0.1:8000
venv/bin/pytest -q --cov --cov-report=term-missing   # fails below 90% (see .coveragerc)
(cd frontend && npm test)                             # vitest; `npm run test:cov` = coverage + 90% gate on src/lib
venv/bin/python -m app.demo_data                      # fake measurements (once per database)
```

Frontend hot reload: `cd frontend && npm run dev` (http://127.0.0.1:5173, proxies `/api` to :8000).

What the runner does: finds a Python 3.10+ that already has the requirements (active venv, `pool_records/venv`,
`pool_records/.venv`, `python3`) or creates `pool_records/venv` with the newest of `python3.13` ... `python3.10`,
`python3` (a venv built with an older Python is recreated); `npm ci` (falls back to `npm install` with a warning if
the lockfile does not fit this npm/platform); `npm run build` (and checks `dist/index.html` exists); `npm test`;
pytest; then it starts uvicorn on `PORT` (8000) until Ctrl+C, with three safety checks
(`scripts/runner_checks.py`, tested in `tests/test_runner_checks.py`):

1. **Port free before starting.** If something already listens on the port (typically an earlier `./for_testing`
   or `uvicorn` still running, maybe from another copy of the project), the run stops with
   `error: port 8000 is already in use: another AquaControl server ...`, shows the process (`lsof` on macOS) and
   suggests `kill <PID>` or `PORT=8001 ./for_testing`. Before this check, the new server failed to bind while the
   old one answered the browser (the "web UI is not built yet" page seen on macOS).
2. **This build is served.** The server is started with `FRONTEND_DIST=<this copy>/frontend/dist` (a
   `FRONTEND_DIST` in `.env` cannot redirect it) and the banner is printed only after `GET /` returned the built
   page; otherwise the run stops with what `/` returned.
3. **`SKIP_FRONTEND` is visible.** If it is set in your environment the run says so at the start and the banner
   says `NOT BUILT: SKIP_FRONTEND is set, only the API works`.

The server also logs `Serving the web UI from <path>` (or `Web UI not built: <path> is missing`) at startup, and
its "not built" answer names the path it looked at, so you can tell which copy of the project is answering.

### macOS (Homebrew)

```bash
xcode-select --install                 # once, if the Command Line Tools are missing (git, compilers)
brew install python@3.12 node@22       # python3.12 is found by name even if `python3` is Apple's 3.9
echo 'export PATH="$(brew --prefix node@22)/bin:$PATH"' >> ~/.zshrc && exec zsh   # node@22 is keg-only
python3.12 --version && node --version && npm --version                          # 3.12.x, v22.x, 10.x+
cd /path/to/workspace && ./for_testing
```

- Newer Node (e.g. 25 from `brew install node`) and npm 11 also work; 22 is the LTS line we recommend.
- An existing `pool_records/venv` created with another Python is reused if it has the requirements; otherwise the
  runner installs into it (or recreates it if it is older than 3.10). To start clean:
  `rm -rf pool_records/venv pool_records/frontend/node_modules`.
- Nothing else is needed (`zip`/`rsync` for `scripts/pack_archive.sh` ship with macOS).

## Demo logins (dummy credentials, password `AquaDemo1!`)

| Email | Role |
|-------|------|
| `admin@aquacontrol.example` | ORG_ADMIN |
| `supervisor@aquacontrol.example` | SUPERVISOR |
| `tech@aquacontrol.example` | TECHNICIAN (read only, except capturing measurements) |

## What exists

- `POST /api/auth/login|logout`, `GET /api/auth/me`, `POST /api/lang`, `GET /api/health`
- `GET /api/dashboard`: counts of clients, pools, users; measurements today and out of range in the last 7 days
- `GET|POST /api/clients`, `GET /api/clients/{id}`; `POST /api/clients/{id}/pools`; `GET /api/pools[?client_id=]`, `GET /api/pools/{id}`
- `GET /api/parameters[?include_inactive=true]`: water parameter catalog (any signed-in user)
- `GET /api/norm-rules`: the organization's norm rules (any signed-in user);
  `PATCH /api/norm-rules/{id}`: edit min/max/active/classification (ORG_ADMIN only)
- `POST /api/measurements`: capture + evaluate (TECHNICIAN, SUPERVISOR, ORG_ADMIN);
  `GET /api/measurements[?pool_id=&parameter_id=&status=&measured_from=&limit=]`, `GET /api/measurements/{id}`
  (any signed-in user)
- Business data is scoped by `organization_id`; write endpoints are guarded by capabilities:

| Capability | Roles | Guards |
|------------|-------|--------|
| `manage_clients` | ORG_ADMIN, SUPERVISOR | `POST /api/clients`, `POST /api/clients/{id}/pools` |
| `manage_norm_rules` | ORG_ADMIN | `PATCH /api/norm-rules/{id}` |
| `capture_measurements` | ORG_ADMIN, SUPERVISOR, TECHNICIAN | `POST /api/measurements` |

- SPA: Login, Layout with nav, Dashboard (with measurement widgets), Clients (list, form, detail with pools), New
  pool form, Measurements (list with status badges and filters, new measurement form with live preview), Norm rules
  (ORG_ADMIN edits inline, other roles read only), Not found

**Language of data vs. UI**: labels, messages and enum values (status, classification, parameter names by code) are
translated by the SPA/API. Free text stored in the database (client and pool names, measurement `notes`, rule
`source_notes`) is shown exactly as stored, in whatever language it was written. The demo organization is Mexican,
so all its seeded and demo text is Spanish; `python -m app.demo_data --lang en` writes English demo notes instead.

Layout:

```text
workspace/
  for_testing                  runner (install, build, test, serve); the only copy
  pool_records/
    app/                       FastAPI backend
      models.py schemas.py serializers.py auth.py deps.py i18n.py seed.py demo_data.py config.py db.py utils.py main.py
      routers/                 thin HTTP layer: auth, core (health, lang, dashboard), clients, pools, parameters,
                               norm_rules, measurements
      services/                validation, queries, commits: clients, pools, parameters, norm_rules, measurements,
                               evaluation (pure), dashboard, scoping
    tests/                     pytest (one file per area; conftest.py isolates the DB and the environment)
    scripts/                   runner_checks.py (port/health/SPA checks for the runner), pack_archive.sh
    frontend/
      src/api/                 fetch client (credentials: include), endpoints, types mirroring the serializers
      src/lib/                 shared logic with vitest tests: evaluation (mirror of the server), format, rules, labels
      src/pages/ components/ hooks/ auth/ i18n/ styles/
      e2e/                     Playwright browser tests (playwright.config.ts)
```

Domain rule violations raise `BusinessError(key)` and become translated JSON (`404` not found, `422` otherwise); see
[Error responses](#error-responses).

## Conventions for new features

- **Module shape**: `routers/<x>.py` (thin: auth dependency + call service + serializer) -> `services/<x>.py`
  (validation, queries, commit) -> `serializers.<x>()` (ORM -> dict, no logic). `frontend/src/api/types.ts`
  mirrors the serializers by hand; `endpoints.ts` wraps the routes.
- **Organization scoping** (`app/services/scoping.py`): read org-owned rows only through
  `scoped_select(Model, org_id)` (lists) and `get_owned(db, Model, org_id, id)` (detail). A foreign id gives the
  same 404 as a missing one. Both raise `TypeError` for global models, so catalogs cannot be "scoped" by mistake.
- **Permissions** (`app/models.py` `CAPABILITIES`): one map from capability to roles. Guard routes with
  `Depends(require_capability("name"))`; unknown names fail at import time. `GET /api/auth/me` returns every
  capability as `can.<name>`, and the SPA uses those flags to hide actions (`Capability` type in `types.ts`).
- **Seeding** (`app/seed.py`): `run_seed` runs on every start and calls independent, idempotent `ensure_*` steps.
  Demo data is created only for an empty DB; catalogs insert missing codes only and never overwrite rows, so a
  database from an older version picks up new catalogs on the next start. There are no migrations:
  `create_all` adds new tables but never new columns, so features add tables instead of altering existing ones.
- **i18n**: server messages in `app/i18n.py`, UI strings in `frontend/src/i18n/{en,es}.ts`; add both languages in
  the same change. Tests fail on a missing key, a dead key, an untranslated Spanish text or a hard-coded label; see
  [Internationalization](#internationalization-enes).
- **Tests with every change**: pytest for the API/services, vitest for `src/lib`, a Playwright spec when a page
  changes behavior; see [Testing](#testing).

## Configuration

Settings come from the environment or `pool_records/.env` (environment wins); see `.env.example` and
`app/config.py`.

| Variable | Default | Meaning |
|----------|---------|---------|
| `SECRET_KEY` | placeholder (warning logged) | signs the session cookie; set a real one outside demos |
| `DATABASE_URL` | `sqlite:///<pool_records>/aquacontrol.db` | SQLAlchemy URL |
| `SESSION_HTTPS_ONLY` | `false` | `true` behind HTTPS |
| `DEMO_PASSWORD` | `AquaDemo1!` | password of the seeded demo users |
| `TIMEZONE` | `America/Mexico_City` | organization zone: folio dates, dashboard days, times shown in the SPA; invalid -> startup error |
| `FRONTEND_DIST` | `frontend/dist` | built SPA to serve (the runner pins it to the folder it built) |
| `PBKDF2_ITERATIONS` | `600000` | password hashing cost (tests lower it) |

Runner-only variables (`../for_testing`): `PYTHON` (interpreter with the requirements), `SKIP_FRONTEND=1` (API only),
`PORT` (default 8000), `E2E_PORT` (default 8765, the `--e2e` server), `PLAYWRIGHT_BROWSERS_PATH` (where Playwright
keeps its browsers, normally not needed).

## Water parameter catalog

`water_parameter` is global reference data (no `organization_id`): pH is pH for every organization. Per
organization norm rules will reference it by `code` later. `GET /api/parameters` returns active rows ordered by
`sort_order` (then `code`); `?include_inactive=true` also returns deactivated ones.

| code | name | unit | decimals | physical min | physical max | sort |
|------|------|------|----------|--------------|--------------|------|
| `PH` | pH | (none) | 1 | 0 | 14 | 10 |
| `FREE_CHLORINE` | Free chlorine | mg/L | 2 | 0 | 20 | 20 |
| `TOTAL_CHLORINE` | Total chlorine | mg/L | 2 | 0 | 20 | 30 |
| `COMBINED_CHLORINE` | Combined chlorine | mg/L | 2 | 0 | 20 | 40 |
| `CYANURIC_ACID` | Cyanuric acid | mg/L | 0 | 0 | 300 | 50 |
| `TURBIDITY` | Turbidity | NTU | 1 | 0 | 100 | 60 |
| `TOTAL_ALKALINITY` | Total alkalinity | mg/L CaCO3 | 0 | 0 | 1000 | 70 |
| `CALCIUM_HARDNESS` | Calcium hardness | mg/L CaCO3 | 0 | 0 | 2000 | 80 |
| `TEMPERATURE` | Temperature | °C | 1 | 0 | 50 | 90 |
| `TDS` | Total dissolved solids | mg/L | 0 | 0 | (none) | 100 |

- `code` is the stable identifier (API, future SPA labels `param.<CODE>`, norm rules). Never rename it.
- `name` is the canonical English label; the SPA will translate by `code` when parameters appear in the UI.
- Physical min/max are plausibility bounds to catch typos (pH 15), **not** regulatory limits. NOM limits belong to
  the per-organization norm rules (next feature step).
- The database enforces a unique `code`, `0 <= decimals <= 4` and `physical_min <= physical_max`.
- To retire a parameter set `active = 0`; the seed will not re-activate it.

## Norm rules (per organization)

`norm_rule` holds the acceptable range of one parameter for one organization (unique per organization +
parameter). Fields: `min_value`, `max_value` (either may be null for a one-sided rule, never both),
`classification` (`NORMATIVE` = limit from a regulation such as a NOM; `COMPLEMENTARY` = good-practice target),
`source_notes` (where the numbers come from and which version), `active` (inactive rules are kept but will be
ignored by evaluation), `updated_at` / `updated_by` (null until an admin edits the seeded default).

### Planning defaults (demo organization)

> **These are PLANNING DEFAULTS, not verified regulatory values.** They let the product be built and demoed.
> Before real use, an ORG_ADMIN must check each value against the current text of NOM-245-SSA1-2010 (and any local
> regulation) and edit it. The NORMATIVE/COMPLEMENTARY split is a planning assumption as well.

The seed gives the demo organization (`laguna-azul`) one rule per catalog parameter. It adds missing rules on
every start and never overwrites existing ones, so admin edits survive restarts. Other organizations get no
defaults (multi-organization is out of scope).

| Parameter | Min | Max | Classification | Active | Note |
|-----------|-----|-----|----------------|--------|------|
| `PH` | 7.2 | 7.8 | NORMATIVE | yes | |
| `FREE_CHLORINE` | 1.0 | 3.0 | NORMATIVE | yes | mg/L |
| `TOTAL_CHLORINE` | | 3.5 | COMPLEMENTARY | **no** | combined chlorine is the controlled value |
| `COMBINED_CHLORINE` | | 0.2 | NORMATIVE | yes | one-sided |
| `CYANURIC_ACID` | | 50 | COMPLEMENTARY | yes | mainly outdoor pools |
| `TURBIDITY` | | 0.5 | NORMATIVE | yes | NTU |
| `TOTAL_ALKALINITY` | 80 | 120 | COMPLEMENTARY | yes | mg/L CaCO3 |
| `CALCIUM_HARDNESS` | 200 | 400 | COMPLEMENTARY | yes | mg/L CaCO3 |
| `TEMPERATURE` | 24 | 30 | COMPLEMENTARY | yes | °C |
| `TDS` | | 1500 | COMPLEMENTARY | **no** | salt pools run far higher |

Every seeded `source_notes` starts with `Valor de planeación, sin verificar: ...` (Spanish, like the demo
organization's other data). The norms page also shows a translated **Planning default, not verified** tag on every
rule nobody has edited yet (`updated_at` null), so the status does not depend on the language of the notes.
Databases seeded before this change keep their English notes (the seed never overwrites rules); delete
`aquacontrol.db` to re-seed.

### API

- `GET /api/norm-rules` (any signed-in user): every rule of the user's organization, active and inactive, in
  parameter `sort_order`. Each row also carries `parameter_code`, `parameter_name`, `unit`, `decimals`.
- `PATCH /api/norm-rules/{id}` (ORG_ADMIN): partial update; send only the keys that change.
  - Editable keys: `min_value`, `max_value`, `active`, `classification`. Any other key -> `422 err.rule_field`
    (`source_notes` is seed/documentation only for now).
  - Bounds accept numbers or text (`"7,4"`); `null` or `""` clears one bound.
  - Validation runs on the stored rule merged with the patch:

| Problem | Status | `key` |
|---------|--------|-------|
| min > max (e.g. only `min_value` sent, above the stored max) | 422 | `err.rule_order` |
| both bounds empty | 422 | `err.rule_bounds` |
| bound outside the parameter's physical range (pH 15) | 422 | `err.rule_range` |
| not a number | 422 | `err.number` |
| classification not NORMATIVE/COMPLEMENTARY (case-insensitive) | 422 | `err.rule_classification` |
| `active` not a JSON boolean | 422 | `err.rule_active` |
| SUPERVISOR / TECHNICIAN | 403 | `forbidden` |
| rule of another organization or unknown id | 404 | `err.not_found` |

  - A patch that changes nothing returns 200 without stamping `updated_at`. A rejected patch changes nothing.
  - The database enforces the same invariants (unique org + parameter, a bound present, min <= max,
    classification values) as a last line of defence.

Example row:

```json
{"id": 1, "code": "PH", "name": "pH", "unit": null, "decimals": 1,
 "physical_min": 0.0, "physical_max": 14.0, "sort_order": 10, "active": true}
```

## Measurements

A `measurement` row is one value of one parameter in one pool:

| Column | Meaning |
|--------|---------|
| `organization_id` | owner; always the recording user's organization |
| `pool_id`, `parameter_id` | the pool (must belong to that organization) and the catalog parameter (must be active) |
| `value` | the reading; input accepts `7.4`, `"7.4"` and `"7,4"` |
| `unit` | copied from the parameter at capture (history keeps it if the catalog changes); null for pH |
| `measured_at` | when the sample was taken (UTC); future times are rejected |
| `notes` | optional, up to 500 characters |
| `folio` | `MES-YYYYMMDD-####`, unique per organization (see below) |
| `recorded_by_id`, `recorded_at` | who saved it and when (UTC) |
| `status`, `direction`, `rule_*` | create-time evaluation and rule snapshot (see below) |

### Folio `MES-YYYYMMDD-####`

- `YYYYMMDD` is the **local date on which the measurement is recorded**, in `TIMEZONE` (default
  `America/Mexico_City`, see `.env.example`). It is not the sampling date: a sample from last week entered today
  gets today's date, so folios follow recording order. At 20:00 in Mexico City (02:00 UTC next day) the folio still
  carries the Mexico City date.
- `####` is a counter per organization and day, starting at `0001`. Past `9999` it keeps growing
  (`MES-20250601-10000`) instead of failing a capture.
- Unique per organization (database constraint). Two simultaneous captures that pick the same number are retried
  (up to 3 attempts). Folios are never reused or changed.
- An invalid `TIMEZONE` stops startup with a clear error.

### Create-time evaluation

Each measurement is evaluated **once, when it is created**, against the organization's **active** norm rule for
its parameter, and the result is stored on the row:

| Situation | `status` | `direction` |
|-----------|----------|-------------|
| `min_value <= value <= max_value` (bounds inclusive; a null bound is open) | `OK` | null |
| `value < min_value` | `OUT_OF_RANGE` | `LOW` |
| `value > max_value` | `OUT_OF_RANGE` | `HIGH` |
| no rule for the parameter, or the rule is inactive | `NO_RULE` | null |

- **Snapshot**: `rule_id`, `rule_min`, `rule_max`, `rule_classification` copy the rule as it was (all null for
  `NO_RULE`). There is no update path and no re-evaluation: a later `PATCH /api/norm-rules/{id}` affects only
  measurements captured afterwards.
- **Where**: `app/services/evaluation.py` has the pure helper `evaluate(value, rule) -> Evaluation` (no DB, no
  clock); `app/services/measurements.py` finds the active rule (`active_rule`) and calls it in `create_measurement`.
- Values are compared exactly as stored (no rounding to the parameter's display `decimals`). A value outside the
  parameter's *physical* range (pH 15) is rejected as a typo (`err.rule_range`); a value outside the *norm* is
  accepted and flagged.
- The database enforces the invariants (valid status; direction only and always for `OUT_OF_RANGE`; a snapshot
  only and always when a rule was used; unique folio per organization and day counter).
- **Write-once**: an ORM `before_update` guard (`app/models.py`, `EVALUATION_COLUMNS`) raises
  `EvaluationIsWriteOnce` if any code tries to change `status`, `direction` or a `rule_*` column of an existing
  measurement. Other columns are not blocked by the guard (there is simply no edit endpoint). Raw SQL is outside
  the ORM and is not guarded.

Requirement -> implementation -> tests:

| Requirement | Where | Tests |
|-------------|-------|-------|
| inside `[min, max]` -> `OK` | `evaluation.evaluate` | `test_evaluation.py::test_value_inside_bounds_is_ok`, `test_bounds_are_inclusive`; `test_measurements.py::test_inside_bounds_is_ok`, `test_bounds_are_inclusive_end_to_end` |
| below min -> `OUT_OF_RANGE` + `LOW` | `evaluation.evaluate` | `test_value_below_min_is_out_of_range_low` (both files) |
| above max -> `OUT_OF_RANGE` + `HIGH` | `evaluation.evaluate` | `test_value_above_max_is_out_of_range_high`, `test_above_max_is_out_of_range_high` |
| no active rule -> `NO_RULE` | `measurements.active_rule` + `evaluate(value, None)` | `test_no_rule_is_no_rule_without_snapshot`, `test_inactive_or_missing_rule_is_no_rule`, `test_rules_of_other_organizations_are_never_used` |
| persist status, direction, rule_id, bounds | `create_measurement` copies `Evaluation` onto the row | the API tests above also read the stored row (`_persisted`) |
| only at create time | single caller of `evaluate`; write-once guard | `test_evaluation_runs_only_when_a_measurement_is_created`, `test_evaluation_columns_are_write_once` |
| rule PATCH does not rewrite history | snapshot columns; no re-evaluation path | `test_editing_the_rule_does_not_rewrite_past_measurements`, `test_rule_patch_sends_no_write_to_the_measurement_table` (no UPDATE/INSERT/DELETE on `measurement` is even sent) |
| pure helper | `app/services/evaluation.py` (no DB, no session, no clock) | `test_evaluation.py` runs on plain objects, no database |

### API

`POST /api/measurements` (TECHNICIAN, SUPERVISOR, ORG_ADMIN):

```json
{"pool_id": 1, "parameter_id": 1, "value": "7,4", "unit": null,
 "measured_at": "2025-06-01T08:30:00-06:00", "notes": "optional"}
```

- `unit` is optional; when sent it must equal the parameter's unit (case-insensitive). No conversions.
- `measured_at` is ISO 8601 **with a time**: `2025-06-01T08:30`, `...:00`, `...:00.123`, with `Z` or `±HH:MM`.
  With an offset it is converted to UTC (`08:30-06:00` -> `14:30Z`); without one it is taken as UTC; omitted
  means now. More than 5 minutes ahead of the server clock is rejected as future (the margin absorbs device clock
  drift). Numbers, date-only and compact (`20250601`) values are rejected on every Python version.

Response (201), also the row shape of `GET /api/measurements` and `GET /api/measurements/{id}`:

```json
{"id": 1, "folio": "MES-20250601-0001", "pool_id": 1, "pool_name": "Semiolímpica", "client_id": 1,
 "client_name": "Club Deportivo Las Palmas", "parameter_id": 1, "parameter_code": "PH", "parameter_name": "pH",
 "unit": null, "decimals": 1, "value": 7.4, "measured_at": "2025-06-01T14:30:00+00:00", "notes": "optional",
 "recorded_at": "...", "recorded_by_id": 3, "recorded_by_name": "Tomás Herrera",
 "status": "OK", "direction": null, "rule_id": 1, "rule_min": 7.2, "rule_max": 7.8, "rule_classification": "NORMATIVE"}
```

Errors are translated (EN/ES) by the session language (`POST /api/lang`), else `Accept-Language`:

| Problem | Status | `key` |
|---------|--------|-------|
| `pool_id` missing or not a positive integer | 422 | `err.pool` |
| pool of another organization or unknown | 404 | `err.not_found` (same answer, nothing revealed) |
| `parameter_id` missing, unknown or inactive | 422 | `err.parameter` |
| value missing / not a number / physically impossible | 422 | `err.value` / `err.number` / `err.rule_range` |
| `unit` differs from the parameter's | 422 | `err.unit` |
| bad `measured_at` / in the future | 422 | `err.measured_at` / `err.measured_future` |
| no session | 401 | |

`GET /api/measurements` (any signed-in user, own organization only): newest first (`measured_at`, then id).
Filters combine with AND: `pool_id`, `parameter_id`, `status` (`OK` / `OUT_OF_RANGE` / `NO_RULE`, case-insensitive;
empty = no filter; anything else -> 422 `err.status_filter`), `measured_from` (ISO 8601 with time, inclusive, e.g.
the dashboard's `windows.today_from`; invalid -> 422 `err.measured_at`), `limit` (default 50, clamped to 1..200).

### Databases from earlier iterations

`./for_testing` keeps `pool_records/aquacontrol.db` between runs. The previous iteration created `measurement` with
another layout (`record_id`, `created_by_id`, no `unit`/`folio`). On startup `app/db.py:upgrade_schema` renames such
an outdated **pre-release** table to `measurement_legacy_<UTC timestamp>` (rows kept) and creates the new one; the
log says `Table measurement had an older layout ... kept as measurement_legacy_...`. Any other table with missing
columns stops startup with a clear message instead of failing later. Deleting `aquacontrol.db` is always safe for
demo data (it is re-seeded).

## SPA: measurement pages

| Route | Page | Loads (existing `api` client, `credentials: "include"`) |
|-------|------|------------------------------------------------------|
| `/measurements[?pool_id=&status=]` | list, newest first, up to 200 rows | `GET /api/pools`, `GET /api/measurements?pool_id=&status=&limit=200` |
| `/measurements/new[?pool_id=]` | new measurement form with live preview | `GET /api/pools`, `GET /api/parameters`, `GET /api/norm-rules` |

Both are in the top nav ("Measurements" / "Mediciones") and available to every role (`capture_measurements`).

**List** (`frontend/src/pages/Measurements.tsx`): folio, measured at (local time) and who recorded it, pool and
client, parameter (translated by code, note in italics), value with unit, the rule **as it was at capture** with
its classification, and a status badge: green `Within range`, red `↓/↑ Out of range (low/high)`, grey dashed
`No rule`. Filters for pool and status are kept in the URL, so a filtered view can be bookmarked or linked. After a
save the list shows `Saved MES-...: <status>.` and the new row on top.

**New measurement**: pool, parameter, value (`7.4` or `7,4`), measured at (`datetime-local`, defaults to now, future
blocked by the browser and by the API), notes. While typing, the **live preview** shows the active rule of the
chosen parameter and what the server will store:

| Typed | Preview |
|-------|---------|
| nothing yet / no parameter | hint |
| `7,4,1`, `abc` | "not a valid number; the server will reject it" |
| `15` for pH | "outside the possible range of pH (0.0 – 14.0)" (server: `err.rule_range`) |
| `7,4` / `6,9` / `8,1` for pH (rule 7.2 – 7.8) | `Within range` / `↓ Out of range (low)` / `↑ Out of range (high)` |
| any value, parameter whose rule is inactive (Total chlorine, TDS) | `No rule` |

Server errors (422) appear under the form in the session language and disappear as soon as a field is edited.

**Shared evaluation helper** (`frontend/src/lib/evaluation.ts`): `parseDecimal`, `evaluate`, `activeRuleFor`,
`isPhysicallyPossible`, `previewMeasurement` mirror `app/utils.parse_float`, `app/services/evaluation.evaluate` and
`create_measurement`. The mirror is enforced, not assumed: `frontend/src/lib/evaluation.cases.json` holds the cases
(inclusive bounds, one-sided rules, no rule, `7,4`, `1_000`, `1e999`, ...) and **both** `tests/test_evaluation.py`
(pytest) and `src/lib/evaluation.test.ts` (vitest) run them; a change on one side that is not made on the other
fails a test suite. The preview uses the rules loaded with the page; the stored result is always the server's.

**Formatting** (`frontend/src/lib/format.ts`) follows the app language, not the browser: English as `en-US`,
Spanish as `es-MX`. Mexico writes decimals with a point (`7.4`, `1,500.5`), so Spanish numbers look like English
ones; dates are localized (`18 nov 2026, 3:53 p.m.`). Values show at least the parameter's decimals and up to 4, so
precision that affected the status is never hidden.

## Demo measurements

```bash
../for_testing --demo-data          # from pool_records/; or, with the app's venv:
venv/bin/python -m app.demo_data [--days 14]
```

`app/demo_data.py` fills the demo organization with about 270 measurements over the last 14 days (deterministic),
all created through the real services so folios, evaluation and snapshots are genuine:

- visits at 09:00 to every pool and 17:30 to Semiolímpica, recorded 10 minutes later by Tomás (technician),
  Sergio (supervisor, afternoons) or Alicia (admin, every 5th day); folios `MES-<day>-0001...` follow the clock;
- a weekly lab panel (alkalinity, hardness, turbidity, TDS), cyanuric acid every 3 days outdoors, total/combined
  chlorine every other day; some values are typed with a decimal comma;
- a new pool **Jacuzzi** (Hotel Brisa Marina) whose 37-38 °C water is `OUT_OF_RANGE HIGH` against the
  temperature rule, with a note explaining why;
- 8 incidents with notes (LOW pH after an acid overdose, HIGH free chlorine after a shock treatment, turbidity,
  cyanuric acid, combined chlorine, ...);
- `NO_RULE` rows for total chlorine and TDS (their planning-default rules are inactive);
- a **PH rule change mid-history**: the loader sets the PH rule to 7.0 – 7.6 for the older half and restores the
  bounds it had before (admin edit through `PATCH` logic), so older PH rows show the 7.0 – 7.6 snapshot and newer
  ones the current rule. One row (note "Fine for today's rule ...", pH 7.7) is HIGH under the old rule although it
  would be OK today: snapshots at work.

It runs once per database (it refuses when the organization already has measurements); delete
`pool_records/aquacontrol.db` to start over. Result of a run on a fresh database: `273 (NO_RULE 37, OK 210,
OUT_OF_RANGE 26)`, 15 folio days, PH snapshots 7.0 – 7.6 (28 rows) and 7.2 – 7.8 (31 rows). Notes are Spanish by
default (free text, shown as stored in both UI languages); `--lang en` writes them in English. Demo data loaded by an
earlier version keeps its English notes: delete `aquacontrol.db` and load again.

## SPA: norm rules page

Route `/norm-rules`, nav "Norm rules" / "Reglas de norma", every role. Data: `GET /api/norm-rules`; edits:
`PATCH /api/norm-rules/{id}` (`frontend/src/pages/NormRules.tsx`).

| Role | Sees |
|------|------|
| ORG_ADMIN (`can.manage_norm_rules`) | the table with an **Edit** button per rule |
| SUPERVISOR, TECHNICIAN | the same table, read only, with the notice "Read only: only organization admins can change rules." (the API answers 403 to their PATCH anyway) |

Columns: parameter (translated, unit, source/version notes), minimum – maximum (`≤ 0.20`, `≥ 650` for one-sided
rules), classification, status (`Active` / `Inactive (not evaluated)`), last change (`Alicia Navarro, <date>` or the
tag `Planning default, not verified`).

Editing (admin): **Edit** turns the row into inputs: minimum and maximum (`7,0` or `7.0`; empty = no limit on that
side), classification, active. **Save** (or Enter) sends only the fields that changed (`src/lib/rules.ts`
`ruleChanges`, vitest-covered) as typed; **Cancel** (or Escape) discards. The server validates (min <= max, at
least one bound, physical range, number format) and its message, in the session language, appears under the row and
disappears as soon as a field changes. Saving without changes sends nothing ("Nothing changed."). After a save the row
shows the new values and who changed them. Rule edits never change past measurements (see "Create-time
evaluation").

## Dashboard widgets

`GET /api/dashboard` (any signed-in user, own organization; computed in `app/services/dashboard.py`):

```json
{"counts": {"clients": 2, "pools": 3, "users": 3},
 "measurements": {"today": 15, "out_of_range_last_7_days": 12},
 "windows": {"timezone": "America/Mexico_City", "today_from": "2026-11-18T06:00:00Z",
             "last_7_days_from": "2026-11-12T06:00:00Z"}}
```

- `today`: measurements whose `measured_at` is on or after local midnight today.
- `out_of_range_last_7_days`: `OUT_OF_RANGE` measurements since local midnight six days ago (today plus the six
  previous days).
- "Local" means `TIMEZONE` (the organization's zone, default `America/Mexico_City`), not UTC and not the browser.
  The window starts are returned as UTC instants with `Z`, safe to put in a URL as-is.
- The counts use `measured_at` (when the sample was taken), not when it was typed in.

The dashboard shows two clickable tiles above the existing counts: **Measurements today** (since <date>) and **Out
of range, last 7 days** (red when above zero). Each links to `/measurements?measured_from=<window start>` (plus
`&status=OUT_OF_RANGE`), which calls `GET /api/measurements` with the same boundaries, so the list shows exactly the
counted rows; a "Measured since ..." chip on the list removes the date filter.

## Error responses

Every error is JSON `{"detail": "<message in the session language>", "key": "<stable key>"}`. Clients should branch
on `key` (stable) and show `detail` (translated: session language from `POST /api/lang`, else `Accept-Language`,
else English). Messages live in `app/i18n.py`.

| Status | `key` | When |
|--------|-------|------|
| 401 | `err.unauthenticated` | no valid session (the SPA goes to the login page) |
| 401 | `login.invalid` | wrong email or password (same answer for both) |
| 403 | `forbidden` | the role lacks the capability (see the capability table in [What exists](#what-exists)) |
| 404 | `err.not_found` | unknown id, or a record of another organization (same answer) |
| 404 | `err.unknown_endpoint` | unknown `/api/...` path |
| 422 | `err.required` | the body is not the expected JSON shape |
| 422 | `err.number` | a number field is not a plain decimal (`7.4`, `7,4`; not `1_000`, `inf`) |
| 422 | `err.client_name`, `err.email` | client create |
| 422 | `err.pool_name`, `err.volume`, `err.environment` | pool create |
| 422 | `err.rule_bounds`, `err.rule_order`, `err.rule_range`, `err.rule_classification`, `err.rule_active`, `err.rule_field` | norm rule PATCH |
| 422 | `err.pool`, `err.parameter`, `err.value`, `err.rule_range`, `err.unit`, `err.measured_at`, `err.measured_future` | measurement create |
| 422 | `err.status_filter`, `err.measured_at` | measurement list filters |

The SPA adds two keys of its own for failures without a server answer: `err.network` (server unreachable) and
`err.http` (an error page that is not JSON, e.g. from a proxy); both are translated in the browser.
`503` ("The web UI is not built yet ...") is a developer message for a missing build and is English only.

## Internationalization (EN/ES)

| What | Where | Translated by |
|------|-------|---------------|
| UI labels, hints, badges, aria-labels | `frontend/src/i18n/{en,es}.ts`, `t("key")` | SPA, current UI language |
| status / direction / classification / environment / parameter names | same dictionaries, by code (`status.OK`, `param.PH`) | SPA |
| API error messages (`detail`) | `app/i18n.py` | server, session language |
| parameter names inside API messages | `app/i18n.py` `param.<CODE>` via `Localized(...)` | server ("... de cloro libre") |
| numbers and dates | `src/lib/format.ts` (`en-US`, `es-MX`) | SPA; times in the organization zone (`user.organization.timezone`) |
| free text stored in the database (client/pool names, notes, rule source notes) | database | not translated: shown as typed (demo data is Spanish; `--lang en` for English demo notes) |

Switching language (EN/ES buttons) updates the UI at once, `<html lang>`, `localStorage` and the server session (so
API messages follow). Spanish is Mexican Spanish: decimal point (`7.4`), dates like `18 nov 2026, 3:53 p.m.`, the
informal "tú", "alberca" for pool.

Adding a string: add the key to **both** `en.ts` and `es.ts` (or both dictionaries in `app/i18n.py` for a server
message) and use it through `t("key")` / `BusinessError("key")`. Guards:

- vitest `src/i18n/i18n.test.ts`: EN/ES have the same keys; `src/i18n/usage.test.ts`: every key used in the code
  exists, no dead keys, same `{placeholders}` in both languages, no hard-coded `aria-label`/`title`;
- pytest `tests/test_i18n.py`: server EN/ES parity and placeholders, no untranslated Spanish text (explicit
  allowlist for "pH", "Folio", ...), every error key used in `app/` exists, every error response is translated
  and keyed, and the SPA has a label for every backend enum value and catalog parameter;
- Playwright `e2e/i18n.spec.ts`: Spanish pages show no English UI text, `<html lang>` follows the switch, Spanish API
  errors and preview in the form.

## Testing

| Layer | Command | What it protects |
|-------|---------|------------------|
| pytest (`tests/`) | `venv/bin/pytest -q` (`--cov` for the 90% gate) | API, roles, organization scoping, validation, evaluation and snapshots, folio, dashboard windows, seeding/demo data, schema upgrade, SPA serving, runner checks, i18n, lockfile and runner hygiene |
| vitest (`frontend/src/**/*.test.ts`) | `npm test` (`npm run test:cov`: 90% gate on `src/lib`) | evaluation mirror, decimal parsing, formatting, rule edit diffs, labels, API client errors, i18n key usage |
| shared contract | both of the above | `frontend/src/lib/evaluation.cases.json` is run by pytest **and** vitest: server and browser preview must agree |
| Playwright (`frontend/e2e/*.spec.ts`) | `../for_testing --e2e` | the real app in Chromium: login for every role, nav and deep links, dashboard widgets vs. the lists they open, measurement list filters, live preview states, save = preview, double-click saves once, stale-preview notice, server errors in the form, norm rule editing and read-only roles, Spanish pages without English text |

`./for_testing --e2e` builds the SPA, installs Chromium for Playwright once (`npx playwright install chromium`,
about 150 MB in the user cache; later runs are a no-op), starts a **second server on `E2E_PORT` (8765) with a
temporary database** loaded with the demo data, runs `npx playwright test`, then deletes that database. Your
`aquacontrol.db` is never touched by the browser tests. On failure, screenshots and traces are in
`frontend/e2e-results/` (`npx playwright show-trace <trace.zip>`). By hand, against a server you can throw away:
`cd frontend && E2E_BASE_URL=http://127.0.0.1:8765 npx playwright test`.

Mutation-checked: removing the double-submit guard makes the "clicked twice" test fail, and hard-coding an English
table header makes the Spanish-page test fail (`/norm-rules: Last change`); the backend evaluation tests were checked
the same way (re-evaluating on read, rewriting history on rule PATCH, removing the write-once guard).

## Robustness and known limits

- Save buttons are disabled while a request is in flight and a second submit is ignored (`src/hooks/useBusy.ts`), so a
  double click creates one measurement (also clients and pools).
- The live preview uses the rules loaded with the form. If an admin changes a rule meanwhile, the stored (server)
  result wins and the confirmation says "The live preview differed ...".
- The measurement list shows the newest 200 rows (API maximum) and says so when a list is cut; there is no paging yet.
- Norm rule edits are last-write-wins (no conflict detection between two admins editing the same rule).
- Measurement create is not idempotent on the server: a client that retries a request after a timeout can create a
  second row (the SPA does not retry).
- Server errors shown in a form disappear when a field is edited (they described the previous attempt).
- An unreachable server or a non-JSON error page gives a translated message instead of the browser's English text.

## Manual verification (besides pytest)

Most of the browser steps below are automated by `./for_testing --e2e`; they are kept for a quick look by hand.

With `./for_testing` (or `./for_testing --cov`) running, or `venv/bin/uvicorn app.main:app`:

```bash
curl -s http://127.0.0.1:8000/api/health                                   # {"status":"ok","app":"AquaControl"}
curl -s -i http://127.0.0.1:8000/api/parameters | head -1                   # HTTP/1.1 401 Unauthorized
curl -s -c jar.txt -H 'Content-Type: application/json' \
     -d '{"login":"tech@aquacontrol.example","password":"AquaDemo1!"}' \
     http://127.0.0.1:8000/api/auth/login   # user JSON, "can":{"manage_clients":false,"manage_norm_rules":false,"capture_measurements":true}
curl -s -b jar.txt http://127.0.0.1:8000/api/parameters                     # 10 rows, PH first, TDS last
curl -s -b jar.txt 'http://127.0.0.1:8000/api/parameters?include_inactive=true'
curl -s -b jar.txt 'http://127.0.0.1:8000/api/parameters?include_inactive=maybe'   # 422, "key":"err.required"
curl -s -b jar.txt -H 'Content-Type: application/json' -d '{"name":"X"}' \
     http://127.0.0.1:8000/api/clients                                      # 403, "key":"forbidden" (technician)
curl -s -b jar.txt http://127.0.0.1:8000/api/norm-rules                     # 10 rules (technicians can read)
curl -s -b jar.txt -X PATCH -H 'Content-Type: application/json' -d '{"active":false}' \
     http://127.0.0.1:8000/api/norm-rules/1                                 # 403 forbidden (technician)
rm -f jar.txt

# as ORG_ADMIN
curl -s -c jar.txt -H 'Content-Type: application/json' \
     -d '{"login":"admin@aquacontrol.example","password":"AquaDemo1!"}' http://127.0.0.1:8000/api/auth/login
curl -s -b jar.txt -X PATCH -H 'Content-Type: application/json' -d '{"min_value":"7,0","max_value":7.6}' \
     http://127.0.0.1:8000/api/norm-rules/1                                 # 200, updated_at + updated_by_name set
curl -s -b jar.txt -X PATCH -H 'Content-Type: application/json' -d '{"min_value":8}' \
     http://127.0.0.1:8000/api/norm-rules/1                                 # 422 err.rule_order (8 > stored max 7.6)
curl -s -b jar.txt -X PATCH -H 'Content-Type: application/json' -d '{"active":true,"classification":"normative"}' \
     http://127.0.0.1:8000/api/norm-rules/10                                # TDS: activated, NORMATIVE
rm -f jar.txt
```

Rule ids follow the seed order on a fresh database (1 = PH ... 10 = TDS); use the `id` from `GET` otherwise.

Measurements (pool 1 = Semiolímpica, parameter 1 = PH, 2 = FREE_CHLORINE, 3 = TOTAL_CHLORINE and rule 1 = PH on a
fresh database). The first PATCH puts PH back to its planning default so the results hold after the edits above:

```bash
B=http://127.0.0.1:8000; J='Content-Type: application/json'
curl -s -c tech.txt -H "$J" -d '{"login":"tech@aquacontrol.example","password":"AquaDemo1!"}' $B/api/auth/login
curl -s -c admin.txt -H "$J" -d '{"login":"admin@aquacontrol.example","password":"AquaDemo1!"}' $B/api/auth/login
curl -s -b admin.txt -X PATCH -H "$J" -d '{"min_value":7.2,"max_value":7.8,"active":true}' $B/api/norm-rules/1

# technician captures; folio MES-<today>-000N, recorded_by_name "Tomás Herrera"
curl -s -b tech.txt -H "$J" -d '{"pool_id":1,"parameter_id":1,"value":"7,4"}' $B/api/measurements           # OK
curl -s -b tech.txt -H "$J" -d '{"pool_id":1,"parameter_id":1,"value":"6.9"}' $B/api/measurements           # OUT_OF_RANGE LOW
curl -s -b tech.txt -H "$J" -d '{"pool_id":1,"parameter_id":2,"value":"3,5","unit":"mg/L"}' $B/api/measurements  # HIGH, unit mg/L
curl -s -b tech.txt -H "$J" -d '{"pool_id":1,"parameter_id":3,"value":2}' $B/api/measurements               # NO_RULE
curl -s -b tech.txt -H "$J" -d '{"pool_id":1,"parameter_id":1,"value":7.4,"measured_at":"2025-06-01T08:30:00-06:00"}' \
     $B/api/measurements                                                   # measured_at 2025-06-01T14:30:00+00:00

# validation (EN, then ES via Accept-Language)
curl -s -b tech.txt -H "$J" -d '{"pool_id":1,"parameter_id":1,"value":7,"measured_at":"2999-01-01T00:00:00Z"}' $B/api/measurements  # 422 err.measured_future
curl -s -b tech.txt -H "$J" -H 'Accept-Language: es' -d '{"pool_id":1,"parameter_id":2,"value":1,"unit":"ppm"}' $B/api/measurements  # 422 err.unit (ES)
curl -s -b tech.txt -H "$J" -H 'Accept-Language: es' -d '{"parameter_id":1,"value":7}' $B/api/measurements      # 422 "Elige una alberca."
curl -s -b tech.txt -H "$J" -d '{"pool_id":999,"parameter_id":1,"value":7}' $B/api/measurements               # 404 err.not_found

# list + filters
curl -s -b tech.txt "$B/api/measurements?pool_id=1&parameter_id=1"
curl -s -b tech.txt "$B/api/measurements?status=OUT_OF_RANGE"
curl -s -b tech.txt "$B/api/measurements?status=NO_RULE"
curl -s -b tech.txt "$B/api/measurements?status=BAD"                   # 422 err.status_filter

# history is not rewritten by rule edits
curl -s -b admin.txt -X PATCH -H "$J" -d '{"min_value":6.5,"max_value":8.5}' $B/api/norm-rules/1
curl -s -b tech.txt "$B/api/measurements?parameter_id=1&status=OUT_OF_RANGE"   # the 6.9 row: still LOW, rule 7.2..7.8
rm -f tech.txt admin.txt
```

In a browser: sign in at http://127.0.0.1:8000/, then open http://127.0.0.1:8000/api/parameters,
http://127.0.0.1:8000/api/norm-rules or http://127.0.0.1:8000/api/measurements in the same browser (the session
cookie is shared). The interactive docs at
http://127.0.0.1:8000/docs use the same cookie: expand `PATCH /api/norm-rules/{rule_id}`, "Try it out", enter an
id and a body such as `{"max_value": 7.6}`, "Execute". Signed in as admin you get 200; as tech, 403. Likewise
`POST /api/measurements` with `{"pool_id": 1, "parameter_id": 1, "value": "8,1"}` returns the folio and the
evaluation for any role.

Measurement pages (after `./for_testing --demo-data`; check the numbers against the API with curl):

```bash
B=http://127.0.0.1:8000; J='Content-Type: application/json'
for path in /measurements /measurements/new; do curl -s -o /dev/null -w "$path %{http_code}\n" $B$path; done   # 200 (SPA)
curl -s -o /dev/null -c tech.txt -H "$J" -d '{"login":"tech@aquacontrol.example","password":"AquaDemo1!"}' $B/api/auth/login
curl -s -b tech.txt "$B/api/measurements?status=OUT_OF_RANGE&limit=200" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))"   # 26
curl -s -b tech.txt "$B/api/measurements?pool_id=3&status=OUT_OF_RANGE&limit=200" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))"   # 15 (Jacuzzi)
curl -s -b tech.txt "$B/api/norm-rules" | python3 -c "import json,sys; print([(r['parameter_code'], r['active']) for r in json.load(sys.stdin)])"
rm -f tech.txt
```

In the browser (http://127.0.0.1:8000, sign in as `tech@aquacontrol.example`):

1. Click **Measurements** in the nav: badges in three colors; "200 shown (newest first)"; Jacuzzi temperature rows
   red with their note; PH rows older than a week show `7.0 – 7.6` in "Rule at capture".
2. Status = **Out of range**: only red rows, as many as the curl above (26); the URL shows `?status=OUT_OF_RANGE`.
   Pool = **Hotel Brisa Marina — Jacuzzi**: 15 rows.
3. **New measurement**: pick Semiolímpica and pH; the preview shows `pH: 7.2 – 7.8 (Normative)`. Type `7,4` (green),
   `6,9` (red, low), `8,1` (red, high), `15` (red text: impossible), `abc` (invalid). Choose Total chlorine: grey
   `No rule`.
4. With pH `8,1` and a note, **Save**: back on the list with `Saved MES-<today>-NNNN: Out of range (high).` and the
   row on top, same status as the preview.
5. New measurement with pH `15`, Save: the server message `15 is outside the possible range of pH.` appears; edit the
   value and it disappears.
6. Switch to **ES**: "Mediciones", "Fuera de rango (bajo)", dates like `18 nov 2026 9:00 a.m.`.

Norm rules page and dashboard widgets (after `./for_testing --demo-data`):

```bash
B=http://127.0.0.1:8000; J='Content-Type: application/json'
for u in tech supervisor admin; do
  curl -s -o /dev/null -c $u.txt -H "$J" -d "{\"login\":\"$u@aquacontrol.example\",\"password\":\"AquaDemo1!\"}" $B/api/auth/login
done
curl -s -b tech.txt $B/api/dashboard | python3 -m json.tool                  # counts, measurements, windows
W=$(curl -s -b tech.txt $B/api/dashboard)
TODAY=$(echo "$W" | python3 -c "import json,sys; print(json.load(sys.stdin)['windows']['today_from'])")
WEEK=$(echo "$W" | python3 -c "import json,sys; print(json.load(sys.stdin)['windows']['last_7_days_from'])")
curl -s -b tech.txt "$B/api/measurements?measured_from=$TODAY&limit=200" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))"                      # = measurements.today
curl -s -b tech.txt "$B/api/measurements?measured_from=$WEEK&status=OUT_OF_RANGE&limit=200" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))"  # = out_of_range_last_7_days
curl -s -w ' [%{http_code}]\n' -b tech.txt -X PATCH -H "$J" -d '{"active":true}' $B/api/norm-rules/10        # 403 (technician)
curl -s -w ' [%{http_code}]\n' -b supervisor.txt -X PATCH -H "$J" -d '{"active":true}' $B/api/norm-rules/10  # 403 (supervisor)
curl -s -w ' [%{http_code}]\n' -b admin.txt -X PATCH -H "$J" -d '{"active":true,"max_value":"2000"}' $B/api/norm-rules/10   # 200, TDS
curl -s -w ' [%{http_code}]\n' -b admin.txt -X PATCH -H "$J" -d '{"active":false,"max_value":1500}' $B/api/norm-rules/10    # back
rm -f tech.txt supervisor.txt admin.txt
```

In the browser:

1. Sign in as **admin**. The dashboard shows **Measurements today** and **Out of range, last 7 days** (red) with
   "Since <date>" and "Days are counted in America/Mexico_City"; the numbers equal the curl above.
2. Click the red tile: the list shows only out-of-range rows, as many as the tile, with a "Measured since ..." chip;
   ✕ on the chip removes the date filter.
3. **Norm rules**: 10 rules, an **Edit** button on each, "Planning default, not verified" tags. Edit pH, type minimum
   `8`, Save: "The minimum must be less than or equal to the maximum." under the row. Type `7,0`: the message goes
   away; Save: "pH rule saved.", the row shows `7.0 – 7.8` and "Alicia Navarro, <now>". Edit + Save without changes:
   "Nothing changed."; Edit + Escape cancels. (Put it back to `7,2` afterwards.)
4. Sign in as **supervisor** or **tech**: same table, notice "Read only: ...", no Edit buttons, no inputs.
5. Switch to **ES**: dashboard "Mediciones de hoy"; **Mediciones** filtered by Jacuzzi shows the note
   "El agua del spa se mantiene a 37-38 °C; ..." (no English text); **Reglas de norma** shows "Solo lectura",
   "Valor de planeación, sin verificar" and Spanish source notes.

To start over with fresh seed data, stop the server and delete `pool_records/aquacontrol.db`.

## Troubleshooting

- Browser shows `{"detail":"The web UI is not built yet. Run: cd frontend && npm install && npm run build ..."}`:
  the server answering is not serving a build. The message ends with `(this server looks for <path>)`; if that
  path is not your copy, an older server is still running: find it with `lsof -nP -iTCP:8000 -sTCP:LISTEN` and stop
  it (`kill <PID>` or Ctrl+C in its terminal), then run `./for_testing` again (it now refuses to start while the port
  is taken). If the path is yours, check `echo $SKIP_FRONTEND` (`unset SKIP_FRONTEND`) and that
  `pool_records/frontend/dist/index.html` exists after the run.

- `./for_testing: No such file or directory` inside `pool_records/`: the runner is one level up; `cd ..` first.
- `./for_testing: Permission denied`: `chmod +x for_testing` (the file is committed as executable; some zip tools
  drop the bit), or run `bash for_testing`.
- `npm ci` fails with `EUSAGE ... Missing: @rollup/rollup-darwin-arm64 ... from lock file` (npm 11): the lockfile
  lacked native builds for other platforms. Fixed: the lock now contains every platform build
  (`tests/test_repo.py::test_lockfile_is_complete_for_every_platform` guards it). If it happens after you change
  dependencies, the runner falls back to `npm install` and warns; commit the updated `package-lock.json`.
  Regenerate locks on a machine with access to the full public registry: a mirror missing some platform packages
  produces an incomplete lock.
- `npm ci` fails with `ETARGET`/`E404`/"not in this registry": the lockfile pins a version the registry does not
  have. Refresh it: `cd frontend && rm -rf node_modules package-lock.json && npm install`, then commit the new lock.
- `npm warn install-scripts ... esbuild (postinstall: node install.js)` (npm 11.2x): informational; esbuild finds
  its binary through its platform package, the build works without the script. `npm install-scripts approve
  esbuild` silences it.
- `error: Python 3.10+ not found (python3 is Python 3.9.x)`: macOS ships 3.9; `brew install python@3.12`.
- `vitest: Permission denied` / `tsc: not found`: `node_modules` is incomplete (usually after a failed install).
  `rm -rf frontend/node_modules` and re-run.
- Startup fails with `Database schema is older than the code`: a table other than the pre-release ones changed;
  delete `pool_records/aquacontrol.db` (demo data is re-seeded) or migrate by hand.
- Startup fails with `TIMEZONE=... is not an IANA time zone`: fix `TIMEZONE` in `.env` (e.g. `America/Mexico_City`).
- `/docs` is blank: FastAPI loads Swagger UI from `cdn.jsdelivr.net`, so the browser needs internet access.
  The API itself works offline; use curl instead.
- `./for_testing --e2e` fails: the failing step and its screenshot/trace are in `pool_records/frontend/e2e-results/`;
  `npx playwright show-trace <path>/trace.zip` replays it. `npx playwright install chromium` needs internet the first
  time. `error: E2E_PORT 8765 is in use`: `E2E_PORT=8766 ./for_testing --e2e`.
- Coverage below 90%: `../for_testing --cov` exits non-zero; the `Missing` column lists uncovered lines.

## Out of scope / later work

Not in this base on purpose:

- Measurement pages beyond this: pagination past 200 rows, date-range and parameter filters in the UI, a detail
  page, dashboard widgets, editing/deleting measurements, a per-organization time zone (one `TIMEZONE` setting)
- React component unit tests (pages are covered by the Playwright suite; their logic lives in `src/lib`, unit-tested)
- Creating/deleting norm rules, editing `source_notes` (API or UI), defaults for other organizations
- More dashboard widgets (per pool, trends), configurable windows
- Langelier Saturation Index calculator and history
- Chemical products, SPIN catalog and dosing estimates
- Maintenance activities and the educational library
- Reports, PDF/Excel export and corrective actions
- Edit/delete for clients and pools, user management, multiple organizations, uploads, PWA/offline
