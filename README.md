# AquaControl (light base)

A small starting point for pool-service management: a FastAPI JSON API and a Vite + React + TypeScript SPA.
It deliberately contains only auth, one organization, clients and pools. Product features are built later (see below).

## Stack

- Backend: FastAPI, SQLAlchemy 2, SQLite, session cookie auth (PBKDF2 hashes in `user_credential`)
- Frontend: Vite, React 18, TypeScript, react-router, EN/ES dictionaries (no UI framework, one CSS file)
- Tests: `pytest` (API, auth, org scoping, SPA serving) and a tiny `vitest` suite (i18n key parity)
- FastAPI serves `frontend/dist` and falls back to `index.html` for non-`/api` paths. No server-rendered pages.

## Quick start

```bash
./for_testing                 # installs deps, builds the SPA, runs pytest + vitest, starts :8000

# or by hand
python3 -m venv venv && venv/bin/pip install -r requirements.txt
(cd frontend && npm install && npm run build)
cp .env.example .env          # set SECRET_KEY
venv/bin/uvicorn app.main:app --reload     # http://127.0.0.1:8000
venv/bin/pytest -q
```

Frontend hot reload: `cd frontend && npm run dev` (http://127.0.0.1:5173, proxies `/api` to :8000).

## Demo logins (dummy credentials, password `AquaDemo1!`)

| Email | Role |
|-------|------|
| `admin@aquacontrol.example` | ORG_ADMIN |
| `supervisor@aquacontrol.example` | SUPERVISOR |
| `tech@aquacontrol.example` | TECHNICIAN (read only) |

## What exists

- `POST /api/auth/login|logout`, `GET /api/auth/me`, `POST /api/lang`, `GET /api/health`
- `GET /api/dashboard` (counts of clients, pools, users)
- `GET|POST /api/clients`, `GET /api/clients/{id}`; `POST /api/clients/{id}/pools`; `GET /api/pools[?client_id=]`, `GET /api/pools/{id}`
- Create endpoints need ORG_ADMIN or SUPERVISOR; everything is scoped by `organization_id`
- SPA: Login, Layout with nav, Dashboard, Clients (list, form, detail with pools), New pool form, Not found

Layout: `app/{models,schemas,serializers,auth,deps,i18n,seed}.py`, `app/routers/`, `app/services/`, `frontend/src/{api,auth,components,hooks,i18n,pages,styles}`.
Domain rule violations raise `BusinessError(key)` and become translated JSON (`404` not found, `422` otherwise).

## Out of scope / later work

Not in this base on purpose:

- Water measurements, parameters, norm rules (NOM) and out-of-range evaluation
- Langelier Saturation Index calculator and history
- Chemical products, SPIN catalog and dosing estimates
- Maintenance activities and the educational library
- Reports, PDF/Excel export and corrective actions
- Edit/delete for clients and pools, user management, multiple organizations, uploads, PWA/offline
