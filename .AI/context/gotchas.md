# Gotchas

## Source Ambiguities

- The brief lists `Driver` as a target user, but the mockups show `Dispatcher`. Treat Dispatcher as the logged-in operational user and Driver as a managed record until confirmed.
- `Drivers On Duty` is ambiguous. The PRD currently maps it to drivers with `On Trip`, but a future product owner may mean available or scheduled drivers.
- Dashboard includes a `region` filter, but the source does not define where region is stored. Decide whether it belongs on vehicle, depot, trip, or multiple entities before implementing filters.

## Dispatch Traps

- Do not rely on filtered dropdowns alone. Always revalidate vehicle and driver eligibility on submit.
- Use a transaction for dispatch. Trip state, vehicle status, and driver status must change together.
- Stale pages are expected. If another dispatcher grabs the same vehicle first, return a helpful conflict message.
- Capacity checks must happen at draft validation and dispatch validation.
- Expired licenses block dispatch even when driver status is `Available`.

## Maintenance Traps

- Creating active maintenance must immediately move the vehicle to `In Shop`.
- Do not allow active maintenance on a vehicle that is currently `On Trip`.
- If overlapping active maintenance is not intentionally supported, block it.
- Closing maintenance should only return a vehicle to `Available` when no other active maintenance exists and the vehicle is not retired.

## Financial And Analytics Traps

- The source defines Operational Cost as `Fuel + Maintenance`, while the UI also captures tolls and other expenses. Label expanded totals clearly if they include more than fuel and maintenance.
- ROI requires revenue, but the core trip fields do not explicitly require it. Add optional trip revenue or define a revenue import/manual entry path.
- Fuel efficiency must not divide by zero. Return `N/A` when liters are zero or missing.
- Use actual completed-trip distance when available; otherwise use odometer deltas with a clear definition.

## RBAC Traps

- Hidden navigation is not security. Enforce permissions on every API mutation and sensitive read.
- A user should not be able to change their own role to gain access.
- Settings and RBAC edits should be audited.

## Data Integrity Traps

- Normalize vehicle registration before uniqueness checks.
- Normalize driver license numbers before uniqueness checks.
- Do not hard-delete completed trips, financial logs, or audit records.
- Retired vehicles should not be selected for new trips and should generally not be reinstated in the MVP.
- Keep status names consistent across code, database, and UI. Drift here will cause subtle dashboard bugs.

## Demo Traps

- Seed data should include invalid and blocked cases, not only happy paths.
- Dashboard totals must match list views; this is one of the quickest ways users spot broken state.
- CSV exports should respect the same filters shown in the UI.
