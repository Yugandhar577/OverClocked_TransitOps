# Architecture

## Architectural Shape

TransitOps should be built as a modular, role-aware web application with a single authoritative backend for operational state. The most important architectural requirement is that business rules live on the server and are protected by database constraints or transactional checks where possible.

The product can be implemented as a monolith for the MVP. Keep domain boundaries clear so the system can grow without needing early microservices.

## Suggested Modules

| Module | Responsibility |
| --- | --- |
| Auth and RBAC | Login, session handling, role permissions, route/API protection. |
| Dashboard | Aggregated KPIs, filters, recent trips, vehicle status distribution. |
| Fleet | Vehicle records, unique registrations, vehicle status lifecycle. |
| Drivers | Driver profiles, license expiry, safety score, eligibility status. |
| Trips | Draft/dispatch/complete/cancel workflow and assignment validation. |
| Maintenance | Service logs and vehicle `In Shop` reservation/release. |
| Finance Ops | Fuel logs, other expenses, costs, ROI inputs. |
| Analytics | Report filters, metric calculations, exports. |
| Settings | Depot name, currency, distance unit, RBAC matrix. |
| Audit | Status-changing event records and before/after state. |

## Core Entities

- `User`: id, name, email, password hash, role, active flag.
- `Role`: id, name, permission set.
- `Vehicle`: registration number, name/model, type, capacity, odometer, acquisition cost, status, region/depot.
- `Driver`: name, license number, license category, license expiry, contact, safety score, status.
- `Trip`: source, destination, vehicle, driver, cargo weight, planned distance, state, timestamps, revenue, final odometer, cancellation reason.
- `MaintenanceLog`: vehicle, service type, status, date, cost, completion date, notes.
- `FuelLog`: vehicle, date, liters, cost, odometer, vendor, optional trip.
- `Expense`: category, amount, date, optional vehicle, optional trip, notes.
- `AuditEvent`: actor, event type, target, timestamp, before/after metadata.

## State Model

Vehicle statuses:

- `Available`: can be selected for dispatch.
- `On Trip`: assigned to a dispatched trip.
- `In Shop`: blocked by active maintenance.
- `Retired`: permanently removed from active use.

Driver statuses:

- `Available`: eligible if license is valid.
- `On Trip`: already assigned to an active trip.
- `Off Duty`: not eligible.
- `Suspended`: blocked until restored by an authorized user.

Trip states:

- `Draft`: editable planned trip.
- `Dispatched`: active trip with reserved vehicle and driver.
- `Completed`: completed delivery; resources released.
- `Cancelled`: stopped trip; resources released if previously dispatched.

## Transaction Rules

The following workflows must be atomic:

- Dispatching a trip: validate trip, vehicle, driver, capacity, and license; set trip to `Dispatched`; set vehicle and driver to `On Trip`.
- Completing a trip: set trip to `Completed`; release vehicle and driver to `Available` unless another valid state applies.
- Cancelling a dispatched trip: set trip to `Cancelled`; release resources.
- Creating active maintenance: set maintenance active and vehicle `In Shop`.
- Closing final active maintenance: set maintenance completed and return vehicle to `Available` unless retired.

Use database transactions and either optimistic locking or equivalent row-level protection so two dispatchers cannot assign the same vehicle or driver from stale pages.

## Validation Boundaries

Client validation is for speed and clarity. Server validation is authoritative.

Hard constraints should include:

- Unique normalized vehicle registration.
- Unique driver license number.
- Non-negative capacity, odometer, acquisition cost, amounts, and distances.
- Positive fuel liters and cost values.
- Foreign-key integrity for trip, maintenance, fuel, and expense links.
- No active dispatch with retired, in-shop, on-trip, or otherwise ineligible resources.

## Metrics

- Fleet Utilization: `On Trip vehicles / Active vehicles * 100`.
- Fuel Efficiency: `Distance traveled / Fuel liters`, with no calculation when liters are zero.
- Operational Cost: `Fuel Cost + Maintenance Cost`.
- Expanded Operating Cost: `Fuel + Maintenance + Tolls + Other Expenses`, if shown.
- ROI: `(Revenue - (Maintenance Cost + Fuel Cost)) / Acquisition Cost * 100`.

Keep metric definitions centralized so dashboard cards, analytics pages, and exports do not drift.
