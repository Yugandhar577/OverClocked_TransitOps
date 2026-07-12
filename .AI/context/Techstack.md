# Tech Stack

No implementation stack is currently committed in the repository. The recommendations below are selected for a fast, reliable hackathon MVP while preserving room for production hardening.

## Recommended Stack

| Layer | Choice | Reason |
| --- | --- | --- |
| Frontend | React with TypeScript | Strong fit for dashboard, forms, tables, and role-aware screens. |
| Build Tool | Vite | Fast local development and simple deployment path. |
| Styling | Tailwind CSS or a small tokenized CSS layer | Efficient responsive UI with consistent status colors and spacing. |
| UI Primitives | Radix UI or accessible custom components | Reliable dialogs, menus, tabs, and form controls. |
| Icons | lucide-react | Clear operational icons with a small footprint. |
| Charts | Recharts | Good enough for KPI cards, revenue trends, utilization, and cost ranking. |
| Backend | Node.js with Express or NestJS | TypeScript end to end; Express for speed, NestJS if stronger structure is desired. |
| ORM | Prisma | Clear schema, migrations, type-safe queries, and transactional support. |
| Database | PostgreSQL | Strong relational constraints for dispatch and financial integrity. SQLite is acceptable only for a local demo. |
| Auth | Session cookies or JWT with refresh strategy | Use HTTP-only secure cookies for production deployment where possible. |
| CSV | Server-generated CSV from filtered query results | Keeps exports consistent with analytics filters. |
| Testing | Vitest/Jest plus Playwright for key flows | Service tests for business rules; browser tests for dispatch workflow. |

## Minimal Hackathon Alternative

For the fastest single-repo build, use:

- Vite + React + TypeScript frontend.
- Express + Prisma backend.
- SQLite during demo development, with schema compatible enough to move to PostgreSQL.
- Seeded users and roles.
- Server-side transactions for dispatch and maintenance even in SQLite.

## Technical Defaults

- Store canonical numeric units: kilometers, kilograms, liters, and base currency minor units or decimal amounts.
- Format currency and distance at the presentation boundary.
- Normalize registration and license identifiers for uniqueness checks.
- Keep permission checks in backend middleware/service functions.
- Centralize status labels, colors, and allowed transitions.
- Use soft-delete or status-based retirement for operational records; do not hard-delete completed trips or financial logs.

## Dependencies To Avoid Unless Needed

- Heavy workflow engines for the MVP state machines.
- Real-time infrastructure before GPS/telematics exists.
- Full accounting packages before finance integration is defined.
- Premature microservices; the product is better served by a well-structured monolith first.
