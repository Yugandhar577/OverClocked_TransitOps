# Codebase And Runtime

## Current Repository State

The repository currently contains planning and source-material files, not an implemented application.

Important paths:

- `.AI/context/PRODUCT_REQUIREMENTS_DOCUMENT.md` - current PRD and product source of truth.
- `.AI/context/*.md` - implementation context for future agents.
- `docs/` - original project brief PDF and UI mockup images.
- `AGENT.md` - repo-level working instructions for future Codex agents.

## Runtime Assumptions

The application scaffold now lives under `SRC/`:

- `SRC/Backend` - FastAPI service and API workflow tests.
- `SRC/Frontend` - Vite + React + TypeScript operations console.

The initial hackathon slice has a seeded in-memory backend repository so the demo works without provisioning infrastructure. Its API services enforce the primary dispatch and maintenance rules. The planned production persistence target remains PostgreSQL through SQLAlchemy async.

Use the selected Python + TypeScript web stack:

- Frontend: Vite + React.
- Backend: FastAPI on Python 3.12 (the local environment currently has Python 3.13; use the pinned dependency set for the demo only).
- Database: PostgreSQL 15 for durable development.
- ORM: SQLAlchemy 2 async + Alembic.
- Tests: Pytest + HTTPX for domain/API rules, Playwright for browser flows.

## Local Development Expectations

Once an app exists, add and maintain:

- `README.md` with setup, environment variables, seed commands, and demo users.
- `.env.example` with safe placeholder values.
- Scripts for install, dev, build, test, lint, migrate, and seed.
- Deterministic seed data that exercises every status and eligibility case.

Recommended script names:

```bash
# Backend, from SRC/Backend
uvicorn app.main:app --reload --port 8000
pytest

# Frontend, from SRC/Frontend
npm run dev
npm run build
```

## Verification Expectations

Before handing off implementation changes:

- Run the fastest relevant tests available.
- Build the app if frontend or shared TypeScript changed.
- Manually verify the dispatch workflow when state-transition logic changes.
- Check responsive behavior for dashboard, tables, trip dispatcher, and forms.
- Confirm generated analytics/export data matches active filters.

## Data And Demo Users

Seed roles should include:

- Fleet Manager.
- Dispatcher.
- Safety Officer.
- Financial Analyst.
- Administrator, if settings and RBAC editing are implemented.

Seed data should include vehicles, drivers, trips, maintenance records, fuel logs, and expenses across valid and invalid states so rule enforcement can be demonstrated quickly.
