# Frontend Reference

## Product Feel

TransitOps is an operational SaaS tool. It should feel calm, dense, and trustworthy: clear navigation, compact controls, readable tables, strong validation, and status visibility. Avoid marketing-style landing pages for the app experience. The first authenticated screen should be the dashboard.

## App Shell

Use a persistent navigation structure with role-filtered entries:

- Dashboard.
- Fleet.
- Drivers.
- Trips.
- Maintenance.
- Fuel & Expenses.
- Analytics.
- Settings.

Desktop can use a left sidebar. Mobile can use a top bar plus drawer or bottom navigation, but must keep primary workflows reachable without hunting.

## Screen Requirements

### Login

- Email and password fields.
- Role selector only if retained from the mockup; otherwise infer role from authenticated user.
- Remember me and Forgot password entry points.
- Clear invalid-login error.
- Lockout or rate-limit messaging after repeated failures.

### Dashboard

- KPI cards for Active Vehicles, Available Vehicles, Vehicles in Maintenance, Active Trips, Pending Trips, Drivers On Duty, and Fleet Utilization.
- Filters for vehicle type, status, and region.
- Recent Trips table with trip ID, vehicle, driver, status, and ETA/status note.
- Vehicle status distribution for Available, On Trip, In Shop, and Retired.

### Fleet

- Search by registration.
- Filters for type and status.
- Table fields: registration, name/model, type, capacity, odometer, acquisition cost, status.
- Clear create/edit/retire actions.
- Retired and In Shop vehicles should be visibly blocked from dispatch.

### Drivers

- Search and filter by status/license state.
- Fields: name, license number, category, expiry, contact, safety score, status.
- Expired licenses and suspended drivers must be visually obvious.
- Safety score can be shown as a compact percentage indicator.

### Trips

- Draft trip form with source, destination, vehicle, driver, cargo weight, and planned distance.
- Vehicle and driver selectors should default to eligible records only.
- Capacity warning must show the exact overage and disable dispatch.
- Lifecycle board or tabs for Draft, Dispatched, Completed, and Cancelled.
- Completion and cancellation flows should use focused dialogs.

### Maintenance

- Active and completed maintenance records.
- Service type, date, cost, vehicle, status, and notes.
- Active maintenance immediately shows the vehicle as `In Shop`.
- Closing maintenance should communicate that the vehicle returns to `Available`.

### Fuel & Expenses

- Separate sections or tabs for fuel logs and other expenses.
- Log Fuel fields: vehicle, date, liters, cost, odometer, vendor, optional trip.
- Add Expense fields: category, amount, date, vehicle/trip link, notes.
- Show total operational cost as Fuel + Maintenance. If other expenses are included, label it as expanded cost.

### Analytics

- Metric cards for Fuel Efficiency, Fleet Utilization, Operational Cost, and ROI.
- Monthly revenue chart.
- Top costliest vehicles ranking.
- Date and vehicle filters.
- CSV export button that exports the active filtered dataset.

### Settings

- Depot name.
- Currency.
- Distance unit.
- RBAC matrix with clear read/write access.

## Visual Language

Recommended status colors:

- Available and Completed: green.
- On Trip and Dispatched: blue.
- In Shop: amber.
- Retired and Cancelled: red.
- Draft and Off Duty: gray.
- Suspended: red or high-warning treatment.

Always pair color with text. Do not rely on color alone.

## Interaction Standards

- Primary actions should be obvious: Add Vehicle, Add Driver, New Trip, Dispatch, Complete, Log Fuel, Add Expense, Export CSV.
- Destructive actions like Retire, Cancel, and Suspend require confirmation.
- Forms should show field-level errors and keep submitted values after validation failure.
- Blocked actions should explain the rule: expired license, suspended driver, vehicle in shop, already on trip, or capacity exceeded.
- Tables should support sorting or at least predictable default ordering.
- Empty states should invite the next useful action.

## Responsive And Accessibility Expectations

- Support 360 px width upward.
- Tables can collapse into cards on mobile, but must preserve status, identifiers, and primary actions.
- Provide visible focus states and keyboard navigation.
- Use semantic labels for inputs, buttons, and status chips.
- Ensure text does not overflow compact buttons or table cells.
- Keep contrast suitable for operational use under bright conditions.
