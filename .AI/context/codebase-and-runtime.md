# Codebase And Runtime

## Current Repository State

The repository currently contains planning and source-material files, not an implemented application.

Important paths:

- `.AI/context/PRODUCT_REQUIREMENTS_DOCUMENT.md` - current PRD and product source of truth.
- `.AI/context/*.md` - implementation context for future agents.
- `docs/` - original project brief PDF and UI mockup images.
- `AGENT.md` - repo-level working instructions for future Codex agents.

## Runtime Assumptions

No package manager files, app framework, database schema, or test runner are present yet. Future implementation work should first inspect the repository and then scaffold the selected stack.

If starting from scratch, prefer a TypeScript web stack:

- Frontend: Vite + React.
- Backend: Express or NestJS.
- Database: PostgreSQL for durable development; SQLite can be used for a demo if setup time is limited.
- ORM: Prisma.
- Tests: Vitest/Jest for domain rules, Playwright for browser flows.

## Local Development Expectations

Once an app exists, add and maintain:

- `README.md` with setup, environment variables, seed commands, and demo users.
- `.env.example` with safe placeholder values.
- Scripts for install, dev, build, test, lint, migrate, and seed.
- Deterministic seed data that exercises every status and eligibility case.

Recommended script names:

```bash
npm run dev
npm run build
npm run test
npm run lint
npm run db:migrate
npm run db:seed
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
