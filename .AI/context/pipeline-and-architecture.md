# Pipeline And Delivery Architecture

## Delivery Strategy

Build the MVP in vertical slices around the operational workflow. The highest-value slice is: authenticate, create vehicle, create driver, create trip, dispatch it, complete it, and see the dashboard update.

Avoid building isolated CRUD screens that do not share state rules. TransitOps succeeds when status transitions and analytics agree.

## Recommended Implementation Order

1. Project scaffold, routing, layout shell, auth foundation, and seed roles.
2. Database schema and core domain services for vehicles, drivers, trips, maintenance, fuel, expenses, users, roles, and audit events.
3. Vehicle and driver management with validations and filters.
4. Trip dispatcher with transactional eligibility checks and lifecycle transitions.
5. Maintenance workflow that blocks and releases vehicles.
6. Fuel and expense modules.
7. Dashboard aggregation and analytics calculations.
8. CSV export, settings, polish, and responsive QA.

## Validation Gates

Before treating a feature as done:

- Server-side permission checks exist for every mutation.
- Business rules are tested at the service/API layer.
- Empty, loading, error, and blocked-action states are visible in the UI.
- State transitions update all related records in one transaction.
- Dashboard and analytics consume committed data rather than mock values.
- Forms reject invalid numeric values and show useful field errors.

## Seed Data

Use realistic seed data so the dashboard, tables, filters, and charts can be visually checked:

- At least 8 vehicles across `Available`, `On Trip`, `In Shop`, and `Retired`.
- At least 8 drivers across `Available`, `On Trip`, `Off Duty`, `Suspended`, and expired-license cases.
- Trips in all lifecycle states.
- Fuel, toll, miscellaneous, and maintenance costs.
- At least one vehicle with enough revenue/cost data to show ROI.

## Testing Priorities

Prioritize tests around rules that prevent operational damage:

- Duplicate vehicle registration is rejected.
- Expired, suspended, off-duty, and already-on-trip drivers cannot dispatch.
- In-shop, retired, and already-on-trip vehicles cannot dispatch.
- Cargo capacity overage blocks dispatch.
- Dispatch, completion, cancellation, and maintenance transitions are atomic.
- CSV export respects active filters.

## Release Checklist

- Authentication protects all non-public routes.
- RBAC hides and blocks unauthorized actions.
- No mock-only data remains in operational screens unless clearly marked as demo seed data.
- Dashboard totals match underlying list views.
- Currency and distance units are consistent across UI and exports.
- Responsive review passes at mobile, tablet, and desktop widths.
- Accessibility basics pass: labels, keyboard navigation, visible focus, contrast, status text.
