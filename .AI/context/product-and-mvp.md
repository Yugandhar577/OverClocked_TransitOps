# Product And MVP

## Product Summary

TransitOps is a responsive fleet-operations web application for logistics teams. It replaces spreadsheets and manual logbooks with one role-aware system for managing vehicles, drivers, trips, maintenance, fuel, expenses, and analytics.

The central product promise is operational correctness: dispatchers should not be able to assign an unavailable vehicle, an ineligible driver, or cargo that exceeds vehicle capacity. Fleet and finance teams should be able to trust that dashboard and analytics numbers come from the same stateful operational records.

## Primary Users

| Role | Purpose | MVP Access |
| --- | --- | --- |
| Fleet Manager | Oversees fleet health, vehicle lifecycle, maintenance impact, and utilization. | Dashboard, fleet registry, maintenance, read analytics. |
| Dispatcher | Creates trips, assigns vehicles and drivers, monitors active deliveries. | Dashboard and trip management. |
| Safety Officer | Maintains compliant driver records and safety visibility. | Driver profiles and compliance views. |
| Financial Analyst | Tracks fuel, maintenance, expenses, operational cost, and ROI. | Fuel/expenses, analytics, exports. |
| Administrator | Optional role for users, settings, and RBAC. | Settings and role configuration. |

Driver records are managed profiles in the MVP, not necessarily login accounts.

## MVP Must Haves

- Email/password authentication with server-enforced RBAC.
- Dashboard with vehicle, trip, driver, and utilization KPIs.
- Vehicle CRUD with unique registration numbers and lifecycle status.
- Driver CRUD with license expiry, safety score, and eligibility status.
- Trip draft, dispatch, complete, and cancel lifecycle.
- Dispatch validation for vehicle availability, driver eligibility, duplicate assignment, license expiry, and cargo capacity.
- Maintenance records that move vehicles into and out of `In Shop`.
- Fuel logs and other expense entries.
- Analytics for fuel efficiency, utilization, operational cost, ROI, revenue trend, and costliest vehicles.
- CSV export for reports.
- Responsive UI suitable for desktop operations and mobile/tablet review.

## Explicit Non-Goals

- Real-time GPS tracking, telematics, and route optimization.
- Customer shipment tracking or proof-of-delivery.
- Payroll, driver shift scheduling, and HR workflows.
- Multi-organization tenancy.
- Accounting-ledger integration.
- Complex approvals and workflow engines.

## Success Criteria

- Invalid dispatch attempts are blocked with plain-language reasons.
- Dispatch, completion, cancellation, and maintenance transitions update related records atomically.
- Dashboard and analytics reflect committed data without manual recalculation.
- Active maintenance immediately removes a vehicle from dispatch eligibility.
- Role permissions are enforced in the API, not only hidden in the UI.
- Core screens remain usable from 360 px mobile width through desktop.

## Product Decisions To Confirm

- Whether drivers need self-service login accounts in addition to managed profiles.
- Whether `Drivers On Duty` means `On Trip`, `Available`, or scheduled for the day.
- Whether trip completion should create a linked fuel log automatically.
- Whether operating cost should remain `Fuel + Maintenance` or include tolls and miscellaneous expenses.
- Where `region` belongs: vehicle, depot, trip, or all three.
- Whether multiple active maintenance work orders per vehicle are allowed. MVP should disallow them.
