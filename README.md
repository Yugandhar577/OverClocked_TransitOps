# TransitOps

TransitOps is an 8-hour hackathon MVP for fleet, driver, trip, maintenance, and operating-cost management.

## What is implemented

- FastAPI API with seeded demo data and protected, role-aware endpoints.
- Server-enforced dispatch rules for vehicle availability, driver status/license expiry, and cargo capacity.
- Atomic-in-intent dispatch, completion, cancellation, and maintenance transitions within the MVP data store.
- Responsive React operations console for Dashboard, Fleet, Drivers, Trips, Maintenance, Finance, Analytics, and Settings.

## Run locally

### Docker

```powershell
docker compose up --build
```

Open `http://localhost:5173`. The API runs at `http://localhost:8000/api`.

### Backend

```powershell
cd SRC/Backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

### Frontend

```powershell
cd SRC/Frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Use `dispatcher@transitops.demo` with any password for the seeded Dispatcher account.

## Notes

The first hackathon slice uses a seeded in-memory repository so the API and UI can be demonstrated immediately without provisioning a database. The API boundary and domain rules are deliberately isolated in `SRC/Backend/app/main.py`; replace the repository with the planned async SQLAlchemy/PostgreSQL adapter before production.
