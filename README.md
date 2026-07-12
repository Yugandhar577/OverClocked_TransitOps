# TransitOps

TransitOps is a smart transport operations platform for fleet, driver, trip, maintenance, live location, and operating-cost management.

## What is implemented

- FastAPI API backed by PostgreSQL, with seeded demo data and protected, role-aware endpoints.
- Server-enforced dispatch rules for vehicle availability, driver status/license expiry, and cargo capacity.
- Atomic-in-intent dispatch, completion, cancellation, and maintenance transitions within the MVP data store.
- Responsive React operations console for Dashboard, Fleet, Drivers, Trips, Maintenance, Finance, Analytics, and Settings.
- Driver-phone live tracking with consent, pause/resume/end controls, offline queueing, idempotent ingestion, route progress, geofences, and freshness alerts.
- Manager live map with authorized fleet filters, SSE updates, REST polling fallback, trip history, and configurable map/directions providers.

## Run locally

### Docker

```powershell
docker compose up --build
```

Open `http://localhost:5173`. The API runs at `http://localhost:8000/api`.
PostgreSQL is exposed on `localhost:5433` to avoid colliding with any existing local PostgreSQL service; its durable Docker volume is named `transitops-postgres-data`.

To use OpenRouteService directions, put `DIRECTIONS_PROVIDER=openrouteservice` and your key in `OPENROUTESERVICE_API_KEY` in the ignored `.env` file. The key is used only by the backend and is never sent to the browser.

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
npm run build
```

The simulator is intentionally disabled when `ENVIRONMENT=production`.

See [Fleet tracking architecture](docs/FLEET_TRACKING.md) and [Location privacy](docs/LOCATION_PRIVACY.md).

## Notes

Alembic migrations create the relational operational and tracking models. Startup seeding is idempotent. To reset local demo data, run `docker compose down -v` and then `docker compose up --build`.
