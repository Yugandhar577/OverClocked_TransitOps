# AGENT.md

## Project

TransitOps is a responsive smart transport operations platform for managing vehicles, drivers, dispatch, maintenance, fuel, expenses, and analytics.

The product source of truth is `.AI/context/PRODUCT_REQUIREMENTS_DOCUMENT.md`. The rest of `.AI/context/` contains implementation summaries and guardrails derived from that PRD. Read those files before making product or architecture decisions.

## Current Repository State

This repository currently contains product context and source materials. No application scaffold is present yet.

Key paths:

- `.AI/context/PRODUCT_REQUIREMENTS_DOCUMENT.md` - full PRD.
- `.AI/context/index.md` - context map.
- `docs/` - original brief PDF and mockup images.

## Working Rules For Agents

- Preserve user changes. Do not revert or overwrite unrelated work.
- Keep business rules on the server; UI validation is only a convenience.
- Use transactions for dispatch, completion, cancellation, and maintenance state changes.
- Enforce RBAC at the API/service layer, not just in navigation.
- Keep dashboard, analytics, exports, and list views aligned with the same data definitions.
- Treat `Dispatcher` as the logged-in trip operations role and `Driver` as a managed profile until the product owner confirms otherwise.

## Product Rules To Protect

- Vehicle registration numbers are unique after normalization.
- Driver license numbers are unique after normalization.
- Retired, In Shop, and On Trip vehicles cannot be dispatched.
- Suspended, Off Duty, On Trip, and expired-license drivers cannot be dispatched.
- Cargo weight cannot exceed vehicle capacity.
- Dispatch moves trip, vehicle, and driver into active states atomically.
- Completion and cancellation release assigned resources atomically.
- Active maintenance moves the vehicle to In Shop; closing final active maintenance returns it to Available unless retired.

## Implementation Preferences

The selected hackathon stack is:

- Vite + React + TypeScript for the frontend.
- FastAPI on Python 3.12 for the backend.
- SQLAlchemy 2 async with PostgreSQL 15 for durable persistence; the first demo slice may use a clearly marked in-memory repository when database provisioning would block a demo.
- Pytest + HTTPX for business-rule/API tests and Playwright for critical browser flows.

Follow `.AI/context/Techstack.md` for pinned versions and dependencies. Do not switch to Express, NestJS, Prisma, or SQLite without an explicit product or delivery reason.

Use the existing project conventions once code exists. Do not introduce a new framework or architecture without a clear reason.

## Verification

For implementation work, verify the smallest meaningful slice:

- Run relevant tests or builds when available.
- Manually check the dispatch workflow after changes to trip, vehicle, driver, or maintenance logic.
- Confirm dashboard and analytics numbers match underlying records.
- Check responsive behavior for dashboard, tables, and operational forms.
