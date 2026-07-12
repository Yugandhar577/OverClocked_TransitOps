# TransitOps

TransitOps is an 8-hour hackathon MVP for fleet, driver, trip, maintenance, and operating-cost management.

## What is implemented

- FastAPI API backed by PostgreSQL, with seeded demo data and protected, role-aware endpoints.
- Server-enforced dispatch rules for vehicle availability, driver status/license expiry, and cargo capacity.
- Atomic-in-intent dispatch, completion, cancellation, and maintenance transitions within the MVP data store.
- Responsive React operations console for Dashboard, Fleet, Drivers, Trips, Maintenance, Finance, Analytics, and Settings.

## Run locally

### Docker

```powershell
docker compose up --build
```

Open `http://localhost:5173`. The API runs at `http://localhost:8000/api`.
PostgreSQL is exposed on `localhost:5433` to avoid colliding with any existing local PostgreSQL service; its durable Docker volume is named `transitops-postgres-data`.

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

Open `http://localhost:5173`. Use `dispatcher@transitops.demo` with password `demo` for the seeded Dispatcher account.

## Notes

The first database migration creates the relational operational model, constraints, and audit log. The API seeds the demo workspace only when the database is empty. To reset local demo data, run `docker compose down -v` and then `docker compose up --build`.
