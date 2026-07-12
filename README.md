# TransitOps

TransitOps is a smart transport operations platform for fleet, driver, trip, maintenance, live location, and operating-cost management.

## What is implemented

- FastAPI API backed by PostgreSQL, with seeded demo data and protected, role-aware endpoints.
- Server-enforced dispatch rules for vehicle availability, driver status/license expiry, and cargo capacity.
- Atomic-in-intent dispatch, completion, cancellation, and maintenance transitions within the MVP data store.
- Responsive React operations console for Dashboard, Fleet, Drivers, Trips, Maintenance, Finance, Analytics, and Settings.
- Driver-phone live tracking with consent, pause/resume/end controls, offline queueing, idempotent ingestion, route progress, geofences, and freshness alerts.
- Manager live map with authorized fleet filters, SSE updates, REST polling fallback, trip history, and configurable map/directions providers.
- Server-composed role dashboards with scoped KPIs, action queues, real data-freshness timestamps, region/vehicle-type filters, and drill-through navigation.
- Page-aware frontend loading: opening one permitted module never preloads unrelated or unauthorized datasets.
- Backend-generated effective permission summaries and role-scoped alerts.

## Roles and access policy

| Role | Main workspace | Read access |
| --- | --- | --- |
| Fleet Manager | Fleet health and maintenance | Fleet, drivers, trips, maintenance, finance, analytics, tracking, settings |
| Dispatcher | Dispatch queue and live operations | Fleet/driver eligibility, trips, tracking; no finance or analytics |
| Safety Officer | Driver compliance and safety risk | Drivers, trips, relevant tracking; no fleet registry or finance |
| Financial Analyst | Cost, revenue, margin, analytics | Aggregated finance and analytics; no full driver/trip/fleet lists |
| Administrator | Platform health and configuration | Authorized cross-module and settings access |
| Driver | Assigned live trip | Own assignment and tracking only |

Navigation reflects these permissions, but the FastAPI permission helpers are authoritative. Unauthorized APIs return `403`; missing authorized records return `404`. Dashboard and alert payloads are composed on the server from the authenticated token, never from a client-supplied role.

## Run locally

### Docker

```powershell
docker compose up --build
```

Open `http://localhost:5173`. The API runs at `http://localhost:8000/api`.
PostgreSQL is exposed on `localhost:5433` to avoid colliding with any existing local PostgreSQL service; its durable Docker volume is named `transitops-postgres-data`.

To use OpenRouteService directions, put `DIRECTIONS_PROVIDER=openrouteservice` and your key in `OPENROUTESERVICE_API_KEY` in the ignored `.env` file. The key is used only by the backend and is never sent to the browser.

Never commit `.env`. If a real key has ever been placed in a shared archive or message, revoke and rotate it in OpenRouteService before continuing to use the integration.

### Backend

```powershell
cd SRC/Backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item ..\..\.env.example ..\..\.env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```powershell
cd SRC/Frontend
npm install
npm run dev
```

Open `http://localhost:5173`. All seeded accounts use password `demo`:

- `fleet@transitops.demo` — fleet manager and settings
- `dispatcher@transitops.demo` — dispatch and depot tracking
- `safety@transitops.demo` — safety tracking
- `driver@transitops.demo` — driver live-trip page
- `finance@transitops.demo` — financial data, no location access

API documentation is available at `http://localhost:8000/docs`.

## Verify and simulate tracking

```powershell
cd SRC/Backend
python -m pytest -q
python scripts/simulate_tracking.py --help
python scripts/simulate_tracking.py --email driver@transitops.demo --password demo

cd ../Frontend
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
```

The Playwright role suite expects the frontend at `http://127.0.0.1:5173` and API at `http://127.0.0.1:8000`; start the Docker stack or both development servers first. It verifies all six demo roles, role-specific landing content, restricted controls, unauthorized startup requests, and a 390 px mobile project.

The simulator is intentionally disabled when `ENVIRONMENT=production`.

See [Fleet tracking architecture](docs/FLEET_TRACKING.md) and [Location privacy](docs/LOCATION_PRIVACY.md).

## Notes

Alembic migrations create the relational operational and tracking models. Startup seeding is idempotent. To reset local demo data, run `docker compose down -v` and then `docker compose up --build`.

Current domain decisions:

- Trip states are `Draft → Dispatched → In Progress → Completed`, with `Cancelled` allowed from active pre-completion states.
- Trip completion may record distance/odometer data; fuel entry remains an explicit, separate finance action.
- Operational cost means fuel + maintenance + tolls + miscellaneous expenses everywhere: Finance, dashboards, Analytics, and filtered CSV exports.
- Region is an operational scope on vehicles and drivers in this MVP; trips inherit scope through their assigned resources instead of storing another mutable region copy.
- Seeded records are labelled as demo data in the UI. Analytics contains no fabricated trend or monthly-revenue series.

Migration `0004_role_aware_dashboards` adds configurable 30/7-day licence-expiry warning thresholds to workspace preferences; dashboard and alert composition otherwise reuse the existing relational schema.
