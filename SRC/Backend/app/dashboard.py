from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Driver, Expense, FuelLog, Maintenance, Preference, Trip, User, Vehicle, VehicleDocument


ROLE_PERMISSIONS: dict[str, set[str]] = {
    "Fleet Manager": {"dashboard.read", "fleet.read", "fleet.manage", "driver.read", "trip.read", "trip.create", "trip.dispatch", "maintenance.read", "maintenance.manage", "finance.read", "analytics.read", "tracking.read", "settings.manage"},
    "Dispatcher": {"dashboard.read", "fleet.read", "driver.read", "trip.read", "trip.create", "trip.dispatch", "tracking.read"},
    "Safety Officer": {"dashboard.read", "driver.read", "trip.read", "tracking.read", "safety.manage"},
    "Financial Analyst": {"dashboard.read", "finance.read", "finance.manage", "analytics.read", "analytics.export"},
    "Administrator": {"dashboard.read", "fleet.read", "fleet.manage", "driver.read", "trip.read", "trip.create", "trip.dispatch", "maintenance.read", "maintenance.manage", "finance.read", "analytics.read", "tracking.read", "settings.manage", "audit.read", "users.manage"},
    "Driver": {"dashboard.read", "driver.home", "trip.own.read", "tracking.own.manage", "issue.create"},
}

RESOURCE_PERMISSION = {
    "vehicles": "fleet.read", "drivers": "driver.read", "trips": "trip.read",
    "maintenance": "maintenance.read", "finance": "finance.read",
    "analytics": "analytics.read", "settings": "settings.manage", "alerts": "dashboard.read",
}


def permissions_for(user: User) -> set[str]:
    return ROLE_PERMISSIONS.get(user.role.name, set())


def can(user: User, permission: str) -> bool:
    return permission in permissions_for(user)


def _kpi(key: str, label: str, value: Any, status: str = "neutral", target: str | None = None) -> dict[str, Any]:
    return {"key": key, "label": label, "value": value, "status": status, "target": target}


async def compose_dashboard(session: AsyncSession, user: User, region: str | None = None, vehicle_type: str | None = None) -> dict[str, Any]:
    role = user.role.name
    if region and role in {"Dispatcher", "Safety Officer"} and user.region and region != user.region:
        raise PermissionError("This role cannot view another region.")
    effective_region = region or (user.region if role in {"Dispatcher", "Safety Officer"} else None)
    all_vehicles = list((await session.scalars(select(Vehicle))).all())
    vehicle_query = select(Vehicle)
    driver_query = select(Driver)
    if effective_region:
        vehicle_query = vehicle_query.where(Vehicle.region == effective_region)
        driver_query = driver_query.where(Driver.region == effective_region)
    if vehicle_type:
        vehicle_query = vehicle_query.where(Vehicle.vehicle_type == vehicle_type)
    vehicles = list((await session.scalars(vehicle_query)).all())
    drivers = list((await session.scalars(driver_query)).all())
    vehicle_ids = {value.id for value in vehicles}
    driver_ids = {value.id for value in drivers}
    trips = list((await session.scalars(select(Trip))).all())
    if vehicle_type:
        trips = [trip for trip in trips if trip.vehicle_id in vehicle_ids]
    elif role in {"Dispatcher", "Safety Officer"} or effective_region:
        trips = [trip for trip in trips if trip.vehicle_id in vehicle_ids or trip.driver_id in driver_ids]
    maintenance = list((await session.scalars(select(Maintenance))).all())
    documents = list((await session.scalars(select(VehicleDocument))).all())
    fuel = list((await session.scalars(select(FuelLog))).all())
    expenses = list((await session.scalars(select(Expense))).all())
    preferences = await session.get(Preference, 1)
    warning_days = preferences.license_expiry_warning_days if preferences else 30
    if effective_region or vehicle_type:
        maintenance = [item for item in maintenance if item.vehicle_id in vehicle_ids]
        documents = [item for item in documents if item.vehicle_id in vehicle_ids]
        fuel = [item for item in fuel if item.vehicle_id in vehicle_ids]
        expenses = [item for item in expenses if item.vehicle_id in vehicle_ids]
    today = date.today()
    active = [trip for trip in trips if trip.status in {"Dispatched", "In Progress"}]
    draft = [trip for trip in trips if trip.status == "Draft"]
    critical_docs = [doc for doc in documents if doc.expiry_date <= today + timedelta(days=warning_days) and doc.status != "Renewed"]
    licence_risks = [driver for driver in drivers if driver.license_expiry <= today + timedelta(days=warning_days)]
    ineligible = [driver for driver in drivers if driver.status == "Suspended" or driver.license_expiry < today]
    active_maintenance = [item for item in maintenance if item.status in {"Scheduled", "In Progress"}]
    operational_cost = sum(item.cost for item in fuel) + sum(item.cost for item in maintenance) + sum(item.amount for item in expenses)
    revenue = sum(trip.revenue for trip in trips if trip.status == "Completed")
    common_tasks: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []

    if role == "Fleet Manager":
        available = sum(vehicle.status == "Available" for vehicle in vehicles)
        kpis = [_kpi("availability", "Fleet availability", f"{round(available / max(1, len(vehicles)) * 100)}%", target="Fleet"), _kpi("utilization", "Utilization", f"{round(len(active) / max(1, len(vehicles)) * 100)}%", target="Fleet Tracking"), _kpi("maintenance", "In maintenance", len(active_maintenance), "warning" if active_maintenance else "good", "Maintenance"), _kpi("documents", "Documents due", len(critical_docs), "critical" if critical_docs else "good", "Fleet"), _kpi("cost", "Operational cost", round(operational_cost, 2), target="Analytics")]
        common_tasks = [{"title": f"{item.service_type} — {item.vehicle_id}", "kind": "maintenance", "severity": "critical" if item.priority == "Urgent" else "warning", "target": "Maintenance"} for item in active_maintenance[:6]]
        widgets = ["fleet_health", "maintenance_backlog", "document_expiry", "cost_summary"]
    elif role == "Dispatcher":
        pairs = min(sum(vehicle.status == "Available" for vehicle in vehicles), sum(driver.status == "Available" and driver.license_expiry >= today for driver in drivers))
        kpis = [_kpi("draft", "Awaiting dispatch", len(draft), "warning" if draft else "good", "Trips"), _kpi("active", "Active trips", len(active), target="Trips"), _kpi("pairs", "Available pairs", pairs, target="Trips"), _kpi("offline", "Tracking exceptions", sum(trip.status == "In Progress" for trip in active), target="Fleet Tracking")]
        common_tasks = [{"title": f"Dispatch {trip.id}: {trip.source} → {trip.destination}", "kind": "trip", "severity": "warning", "target": "Trips", "record_id": trip.id} for trip in draft[:6]]
        widgets = ["dispatch_queue", "live_operations", "driver_availability"]
    elif role == "Safety Officer":
        high_risk = [driver for driver in drivers if driver.safety_score < 80]
        kpis = [_kpi("licences", "Licence risks", len(licence_risks), "critical" if licence_risks else "good", "Drivers"), _kpi("risk", "High-risk drivers", len(high_risk), "critical" if high_risk else "good", "Drivers"), _kpi("suspended", "Suspended drivers", sum(driver.status == "Suspended" for driver in drivers), "warning", "Drivers"), _kpi("ineligible", "Ineligible for dispatch", len(ineligible), "critical" if ineligible else "good", "Drivers")]
        common_tasks = [{"title": f"Review {driver.name}: score {driver.safety_score}", "kind": "driver", "severity": "critical", "target": "Drivers", "record_id": driver.id} for driver in sorted(high_risk + licence_risks, key=lambda item: item.safety_score)[:6]]
        widgets = ["driver_risk", "licence_expiry", "dispatch_eligibility"]
    elif role == "Financial Analyst":
        margin = revenue - operational_cost
        kpis = [_kpi("operating_cost", "Operating cost", round(operational_cost, 2), target="Fuel & Expenses"), _kpi("fuel", "Fuel cost", round(sum(item.cost for item in fuel), 2), target="Fuel & Expenses"), _kpi("revenue", "Completed-trip revenue", round(revenue, 2), target="Analytics"), _kpi("margin", "Gross margin", round(margin, 2), "critical" if margin < 0 else "good", "Analytics")]
        common_tasks = [{"title": "Review uncategorized and miscellaneous expenses", "kind": "finance", "severity": "warning", "target": "Fuel & Expenses"}] if any(item.category == "Miscellaneous" for item in expenses) else []
        widgets = ["cost_breakdown", "revenue_margin", "vehicle_cost_ranking"]
    elif role == "Administrator":
        active_users = len(list((await session.scalars(select(User).where(User.active.is_(True)))).all()))
        kpis = [_kpi("users", "Active users", active_users, target="Settings"), _kpi("tracking", "Active tracking", len(active), target="Fleet Tracking"), _kpi("quality", "Data-quality issues", len(critical_docs) + len(licence_risks), "warning", "Settings"), _kpi("health", "API health", "Operational", "good")]
        common_tasks = [{"title": "Review workspace roles and tracking policy", "kind": "admin", "severity": "neutral", "target": "Settings"}]
        widgets = ["system_health", "data_quality", "permission_summary"]
    else:
        own_trip = next((trip for trip in active if trip.driver_id == user.driver_id), None)
        kpis = [_kpi("trip", "Active assignment", own_trip.id if own_trip else "None", "good" if own_trip else "neutral", "My Live Trip"), _kpi("vehicle", "Assigned vehicle", own_trip.vehicle_id if own_trip else "Unassigned", target="My Live Trip")]
        common_tasks = [{"title": "Open your assigned trip and confirm GPS status", "kind": "driver", "severity": "neutral", "target": "My Live Trip"}] if own_trip else []
        widgets = ["driver_assignment", "pre_trip_status"]

    for item in common_tasks:
        if item["severity"] in {"critical", "warning"}:
            alerts.append(item)
    return {
        "role": role,
        "generated_at": datetime.now(UTC).isoformat(),
        "scope": {"region": effective_region, "vehicle_type": vehicle_type, "depot": None},
        "filter_options": {
            "regions": sorted({vehicle.region for vehicle in all_vehicles if vehicle.region and (role not in {"Dispatcher", "Safety Officer"} or not user.region or vehicle.region == user.region)}),
            "vehicle_types": sorted({vehicle.vehicle_type for vehicle in all_vehicles}),
        },
        "permissions": sorted(permissions_for(user)),
        "kpis": kpis,
        "tasks": common_tasks,
        "alerts": alerts,
        "widgets": widgets,
    }
