# Tech Stack

TransitOps is an 8-hour hackathon build. Favor boring, proven, pinned dependencies and a simple full-stack shape over clever abstractions. Do not bump versions or add major dependencies during the hackathon unless the change is required to unblock delivery and the full test/build path is rerun.

## Architecture Choice

| Area | Choice | Why It Fits TransitOps |
| --- | --- | --- |
| Backend | FastAPI on Python 3.12 | Fast API development, strong request validation, good fit for rule-heavy dispatch workflows. |
| Database | PostgreSQL 15 | Relational constraints and transactions are important for vehicle, driver, trip, maintenance, and finance integrity. |
| ORM | SQLAlchemy 2 async + Alembic | Explicit transactions for dispatch/maintenance, migration support, async API compatibility. |
| Auth | JWT with hashed passwords | Fast to implement for the MVP; keep token handling centralized and protected. |
| Frontend | React 18 + TypeScript + Vite | Fast UI delivery for dashboards, forms, tables, and operational boards. |
| Styling | Tailwind CSS 3.4 | Quick responsive layout and consistent status styling. |
| Forms | React Hook Form + Zod | Ergonomic form validation; mirror backend Pydantic schemas where useful. |
| Charts | Recharts | Enough for KPI cards, revenue trend, utilization, ROI, and costliest vehicles. |
| Email | aiosmtplib + Mailhog | Supports bonus license-expiry reminders without external email risk. |
| E2E | Playwright | Verify the critical app workflow: login, create records, dispatch, complete, view dashboard. |

## Backend

| Package | Version | Purpose | Notes |
| --- | --- | --- | --- |
| `python` | `3.12.x` | Runtime | Do not use Python 3.13 during the hackathon. |
| `fastapi` | `0.115.0` | HTTP framework | Requires Pydantic v2. |
| `uvicorn[standard]` | `0.30.6` | ASGI server | Use `--reload` in dev; avoid multi-worker debugging locally. |
| `sqlalchemy` | `2.0.35` | ORM | Use async API only: `AsyncSession`, `select()`, `update()`. |
| `asyncpg` | `0.29.0` | PostgreSQL driver | DSN format: `postgresql+asyncpg://...`. |
| `alembic` | `1.13.3` | Migrations | Configure async migration environment. |
| `pydantic` | `2.9.2` | API schemas | Use v2 syntax: `model_config = ConfigDict(...)`. |
| `pydantic-settings` | `2.5.2` | Environment config | `BaseSettings` lives here. |
| `python-jose[cryptography]` | `3.3.0` | JWT | Use `jose.jwt.encode/decode`. |
| `passlib[bcrypt]` | `1.7.4` | Password hashing | Keep paired with `bcrypt==4.0.1`. |
| `bcrypt` | `4.0.1` | Hash implementation | Avoid bcrypt 4.1+ passlib warning churn. |
| `aiosmtplib` | `3.0.2` | Async SMTP | Works with Mailhog for bonus reminders. |
| `email-validator` | `2.2.0` | Email validation | Required by Pydantic `EmailStr`. |
| `python-multipart` | `0.0.9` | Form parsing | Required if FastAPI `Form()` is used. |
| `httpx` | `0.27.2` | Test client and HTTP | Use for backend API tests where practical. |

### Backend Dev/Test

| Package | Version | Purpose |
| --- | --- | --- |
| `pytest` | `8.3.3` | Test runner |
| `pytest-asyncio` | `0.24.0` | Async test support |
| `pytest-cov` | `5.0.0` | Coverage |
| `freezegun` | `1.5.1` | Time mocking |
| `factory-boy` | `3.3.1` | Test fixtures |

Set `asyncio_mode = "auto"` in `pyproject.toml`.

## Database

| Component | Version | Notes |
| --- | --- | --- |
| PostgreSQL | `15.x` | Use image `postgres:15-alpine` in Docker Compose. |

No Redis, queue broker, or database extensions are required for the MVP.

## Frontend

| Package | Version | Purpose | Notes |
| --- | --- | --- | --- |
| `node` | `20.x LTS` | Runtime | Do not use Node 22 for this build. |
| `react` | `18.3.1` | UI library | Hooks only; no class components. |
| `react-dom` | `18.3.1` | Renderer | Keep paired with React version. |
| `react-router-dom` | `6.26.x` | Routing | Use v6 APIs. |
| `vite` | `5.4.x` | Build tool | Use React TypeScript template. |
| `typescript` | `5.5.x` | Types | Use `strict: true`. |
| `tailwindcss` | `3.4.x` | Styling | Use Tailwind 3 config, not Tailwind 4. |
| `postcss` | `8.4.x` | Tailwind dependency | Required by Tailwind. |
| `autoprefixer` | `10.4.x` | CSS prefixes | Required by Tailwind. |
| `axios` | `1.7.x` | HTTP client | Use one configured API instance. |
| `react-hook-form` | `7.53.x` | Form state | Good fit for dense operational forms. |
| `@hookform/resolvers` | `3.9.x` | RHF + Zod | Use `zodResolver(schema)`. |
| `zod` | `3.23.x` | Runtime validation | Mirror Pydantic constraints where useful. |
| `react-day-picker` | `9.1.x` | Calendar/date picker | Use with date-fns. |
| `date-fns` | `3.6.x` | Date utilities | Do not add Moment. |
| `lucide-react` | `0.451.x` | Icons | Use for buttons and navigation. |
| `recharts` | `2.12.x` | Charts | Load mainly on analytics/reporting screens. |
| `clsx` | `2.1.x` | Conditional classes | Keep styling logic tidy. |

### Frontend Dev/Test

| Package | Version | Purpose |
| --- | --- | --- |
| `@playwright/test` | `1.47.x` | E2E tests |
| `@vitejs/plugin-react` | `4.3.x` | Vite React plugin |
| `eslint` | `9.x` | Linting |
| `eslint-plugin-react-hooks` | `5.x` | Hook rules |
| `prettier` | `3.3.x` | Formatting |

Run `npx playwright install` after frontend dependencies are installed if E2E tests are used.

## Optional API Test Layer

The attached stack includes a separate Node API test layer at `SRC/Backend/tests/api/`.

| Package | Version | Purpose |
| --- | --- | --- |
| `jest` | `29.x` | Test runner |
| `supertest` | `7.x` | HTTP assertions |
| `@types/jest` | `29.x` | Jest types |
| `@types/supertest` | `6.x` | Supertest types |
| `ts-jest` | `29.x` | TypeScript transform |
| `jsonwebtoken` | `9.x` | Mint test JWTs |

For an 8-hour build, prefer Python `pytest + httpx` unless the team specifically wants black-box Node API tests. Keep this layer optional so it does not slow the core delivery path.

## Infrastructure

| Component | Version | Notes |
| --- | --- | --- |
| Docker | Latest | Required for local compose setup. |
| Docker Compose | v2 plugin | Use `docker compose`, not legacy `docker-compose`. |
| Mailhog | `mailhog/mailhog:latest` | SMTP capture; web UI normally on port `8025`. |

## Hackathon Folder Layout

Use this layout unless implementation work reveals a stronger reason to change it:

```text
SRC/
  Backend/
    app/
    alembic/
    tests/
  Frontend/
    src/
    tests/
```

## Install Commands

Backend:

```bash
cd SRC/Backend
python -m venv .venv
pip install fastapi==0.115.0 "uvicorn[standard]"==0.30.6 sqlalchemy==2.0.35 asyncpg==0.29.0 alembic==1.13.3 pydantic==2.9.2 pydantic-settings==2.5.2 "python-jose[cryptography]"==3.3.0 "passlib[bcrypt]"==1.7.4 bcrypt==4.0.1 aiosmtplib==3.0.2 email-validator==2.2.0 python-multipart==0.0.9 httpx==0.27.2
pip install pytest==8.3.3 pytest-asyncio==0.24.0 pytest-cov==5.0.0 freezegun==1.5.1 factory-boy==3.3.1
```

Frontend:

```bash
cd SRC/Frontend
npm create vite@latest . -- --template react-ts
npm install react-router-dom@6.26 axios@1.7 react-hook-form@7.53 @hookform/resolvers@3.9 zod@3.23 react-day-picker@9.1 date-fns@3.6 lucide-react@0.451 recharts@2.12 clsx@2.1
npm install -D tailwindcss@3.4 postcss@8.4 autoprefixer@10.4 @playwright/test@1.47 @vitejs/plugin-react@4.3 eslint@9 eslint-plugin-react-hooks@5 prettier@3.3 typescript@5.5
```

Optional Node API tests:

```bash
cd SRC/Backend/tests/api
npm init -y
npm install -D jest@29 supertest@7 @types/jest@29 @types/supertest@6 ts-jest@29 typescript@5.5 jsonwebtoken@9
```

## Do Not Add During The 8-Hour Build

- Redux, Zustand, MobX, React Query, or SWR.
- Material UI, Chakra, Mantine, or another component framework.
- Celery, RQ, Dramatiq, Redis, or a queue broker.
- Sentry, Datadog, or observability platforms.
- Stripe, Razorpay, or live payment SDKs.
- Microservices or separate deployable services beyond frontend, backend, Postgres, and optional Mailhog.

## Delivery Guidance

Build the smallest vertical slice first:

1. Login with seeded roles.
2. Vehicle and driver CRUD.
3. Trip dispatch with server-side eligibility checks.
4. Completion/cancellation state transitions.
5. Maintenance `In Shop` blocking.
6. Dashboard and analytics from real data.
7. Fuel/expense logs and CSV export.

The stack is a good fit as long as the implementation stays focused on the PRD's core operational workflow.
