from datetime import date, datetime

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Driver, Expense, FuelLog, Maintenance, Preference, Role, Trip, User, Vehicle


password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def seed_demo_data(session: AsyncSession) -> None:
    """Create a deterministic demo workspace only when the database is empty."""
    if await session.scalar(select(User.id).limit(1)):
        return

    roles = [
        Role(id="role-fleet", name="Fleet Manager"),
        Role(id="role-dispatch", name="Dispatcher"),
        Role(id="role-safety", name="Safety Officer"),
        Role(id="role-finance", name="Financial Analyst"),
        Role(id="role-admin", name="Administrator"),
    ]
    password_hash = password_context.hash("demo")
    users = [
        User(id="u-fleet", name="Raven Kapoor", email="fleet@transitops.demo", password_hash=password_hash, role_id="role-fleet"),
        User(id="u-dispatch", name="Aarav Shah", email="dispatcher@transitops.demo", password_hash=password_hash, role_id="role-dispatch"),
        User(id="u-safety", name="Priya Iyer", email="safety@transitops.demo", password_hash=password_hash, role_id="role-safety"),
        User(id="u-finance", name="Ishaan Mehta", email="finance@transitops.demo", password_hash=password_hash, role_id="role-finance"),
    ]
    vehicles = [
        Vehicle(id="v-van05", registration="GJ 01 AB 1234", registration_normalized="GJ01AB1234", name="Van-05", vehicle_type="Van", capacity_kg=500, odometer_km=42850, acquisition_cost=850000, region="Ahmedabad", status="Available"),
        Vehicle(id="v-truck11", registration="GJ 01 CD 8871", registration_normalized="GJ01CD8871", name="Truck-11", vehicle_type="Truck", capacity_kg=5000, odometer_km=119340, acquisition_cost=2250000, region="Ahmedabad", status="On Trip"),
        Vehicle(id="v-mini03", registration="GJ 27 MN 2203", registration_normalized="GJ27MN2203", name="Mini-03", vehicle_type="Mini Truck", capacity_kg=1200, odometer_km=67830, acquisition_cost=1180000, region="Surat", status="In Shop"),
        Vehicle(id="v-car02", registration="GJ 01 EF 4132", registration_normalized="GJ01EF4132", name="Car-02", vehicle_type="Car", capacity_kg=300, odometer_km=91500, acquisition_cost=620000, region="Ahmedabad", status="Retired"),
    ]
    drivers = [
        Driver(id="d-alex", name="Alex Thomas", license_number="GJ-DRV-1088", license_normalized="GJ-DRV-1088", license_category="LMV", license_expiry=date(2027, 10, 14), contact="+91 98765 32010", safety_score=94, status="Available", region="Ahmedabad"),
        Driver(id="d-rahul", name="Rahul Patel", license_number="GJ-DRV-1205", license_normalized="GJ-DRV-1205", license_category="HMV", license_expiry=date(2027, 3, 22), contact="+91 98765 10222", safety_score=88, status="On Trip", region="Ahmedabad"),
        Driver(id="d-neha", name="Neha Desai", license_number="GJ-DRV-1779", license_normalized="GJ-DRV-1779", license_category="LMV", license_expiry=date(2025, 12, 8), contact="+91 98765 76111", safety_score=91, status="Off Duty", region="Surat"),
        Driver(id="d-samir", name="Samir Khan", license_number="GJ-DRV-1882", license_normalized="GJ-DRV-1882", license_category="HMV", license_expiry=date(2027, 6, 1), contact="+91 98765 45789", safety_score=72, status="Suspended", region="Ahmedabad"),
    ]
    trips = [
        Trip(id="TR-1042", source="Ahmedabad Depot", destination="Vadodara Hub", vehicle_id="v-truck11", driver_id="d-rahul", cargo_kg=3200, planned_distance_km=112, revenue=18500, notes="Priority retail replenishment", status="Dispatched", created_at=datetime(2026, 7, 12, 8, 15)),
        Trip(id="TR-1043", source="Ahmedabad Depot", destination="Gandhinagar", vehicle_id="v-van05", driver_id="d-alex", cargo_kg=420, planned_distance_km=38, revenue=7200, notes="Draft delivery plan", status="Draft", created_at=datetime(2026, 7, 12, 9, 10)),
        Trip(id="TR-1039", source="Surat", destination="Bharuch", vehicle_id="v-mini03", driver_id="d-neha", cargo_kg=700, planned_distance_km=78, actual_distance_km=81, revenue=12400, notes="Completed before workshop booking", status="Completed", created_at=datetime(2026, 7, 10, 7), completed_at=datetime(2026, 7, 10, 12, 30)),
    ]
    maintenance = [
        Maintenance(id="m-1", vehicle_id="v-mini03", service_type="Brake inspection", cost=18000, status="Active", opened_at=date(2026, 7, 11), notes="Workshop diagnosis in progress"),
        Maintenance(id="m-2", vehicle_id="v-truck11", service_type="Oil change", cost=6400, status="Completed", opened_at=date(2026, 6, 20), closed_at=date(2026, 6, 21), notes="Scheduled service"),
    ]
    fuel_logs = [
        FuelLog(id="f-1", vehicle_id="v-van05", logged_at=date(2026, 7, 5), liters=42, cost=3150, odometer_km=42790, vendor="HP Fuel"),
        FuelLog(id="f-2", vehicle_id="v-truck11", trip_id="TR-1042", logged_at=date(2026, 7, 6), liters=110, cost=8400, odometer_km=118990, vendor="Indian Oil"),
        FuelLog(id="f-3", vehicle_id="v-mini03", trip_id="TR-1039", logged_at=date(2026, 7, 6), liters=28, cost=2050, odometer_km=67790, vendor="Shell"),
    ]
    expenses = [
        Expense(id="e-1", category="Toll", amount=340, vehicle_id="v-truck11", trip_id="TR-1042", logged_at=date(2026, 7, 11), notes="Expressway"),
        Expense(id="e-2", category="Miscellaneous", amount=150, vehicle_id="v-van05", trip_id="TR-1043", logged_at=date(2026, 7, 10), notes="Loading supplies"),
    ]
    # Flush parent tables before adding records that reference them. The explicit
    # order mirrors the database foreign-key graph and keeps seeding portable.
    session.add_all(roles)
    await session.flush()
    session.add_all([*users, *vehicles, *drivers])
    await session.flush()
    session.add_all([*trips, *maintenance])
    await session.flush()
    session.add_all([*fuel_logs, *expenses, Preference(id=1, depot_name="Gandhinagar Depot, Gujarat", currency="INR", distance_unit="Kilometres")])
