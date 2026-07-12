# TransitOps Context Index

This folder is the working memory for TransitOps, a smart transport operations platform for fleet, driver, dispatch, maintenance, fuel, expense, and analytics workflows.

Use `PRODUCT_REQUIREMENTS_DOCUMENT.md` as the product source of truth. The companion files below are implementation-oriented summaries derived from that PRD.

## Files

- `PRODUCT_REQUIREMENTS_DOCUMENT.md` - Full PRD, requirements, business rules, entities, acceptance scenarios, priorities, and traceability.
- `product-and-mvp.md` - Product intent, MVP boundaries, roles, success criteria, and open product decisions.
- `ARCHITECTURE.md` - Recommended domain architecture, state transitions, data model boundaries, and integrity rules.
- `pipeline-and-architecture.md` - Delivery workflow, implementation sequencing, validation gates, and release checklist.
- `Techstack.md` - Suggested stack and technical defaults for a hackathon-friendly responsive web application.
- `codebase-and-runtime.md` - Current repository state, expected runtime setup, local development conventions, and verification commands.
- `FRONTEND_REFERENCE.md` - UI structure, screen-by-screen behavior, visual language, accessibility, and responsive expectations.
- `gotchas.md` - Known ambiguities, edge cases, and traps that future agents should handle deliberately.

## Current Product Decision

The source material conflicts on whether the operational application role is `Driver` or `Dispatcher`. Until confirmed, treat `Dispatcher` as the logged-in role that creates and dispatches trips, and treat `Driver` as a managed operational profile.

## Source Material

- Product brief PDF and UI mockups are in `docs/`.
- The comprehensive synthesized PRD is in `.AI/context/PRODUCT_REQUIREMENTS_DOCUMENT.md`.
