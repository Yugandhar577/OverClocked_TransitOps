from datetime import date, datetime, timedelta
import os

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    Driver,
    DriverTrackingSession,
    Expense,
    FuelLog,
    Geofence,
    LatestVehicleLocation,
    Maintenance,
    Preference,
    Role,
    Trip,
    User,
    Vehicle,
    VehicleLocationPoint,
    utc_now,
)


password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def seed_demo_data(session: AsyncSession) -> None:
    """Create and incrementally upgrade the deterministic demo workspace."""
    if not await session.scalar(select(User.id).limit(1)):
        await seed_core_data(session)
    await seed_tracking_data(session)


async def seed_core_data(session: AsyncSession) -> None:
    roles = [
        Role(id="role-fleet", name="Fleet Manager"),
        Role(id="role-dispatch", name="Dispatcher"),
        Role(id="role-safety", name="Safety Officer"),
        Role(id="role-finance", name="Financial Analyst"),
        Role(id="role-admin", name="Administrator"),
        Role(id="role-driver", name="Driver"),
    ]
    password_hash = password_context.hash("demo")
    users = [
        User(id="u-fleet", name="Raven Kapoor", email="fleet@transitops.demo", password_hash=password_hash, role_id="role-fleet", region="Ahmedabad"),
        User(id="u-dispatch", name="Aarav Shah", email="dispatcher@transitops.demo", password_hash=password_hash, role_id="role-dispatch", region="Ahmedabad"),
        User(id="u-safety", name="Priya Iyer", email="safety@transitops.demo", password_hash=password_hash, role_id="role-safety", region="Ahmedabad"),
        User(id="u-finance", name="Ishaan Mehta", email="finance@transitops.demo", password_hash=password_hash, role_id="role-finance", region="Ahmedabad"),
        User(id="u-admin", name="Devika Rao", email="admin@transitops.demo", password_hash=password_hash, role_id="role-admin", region=None),
    ]
    vehicles = [
        Vehicle(id="v-van05", registration="GJ 01 AB 1234", registration_normalized="GJ01AB1234", name="Van-05", vehicle_type="Van", capacity_kg=500, odometer_km=42850, acquisition_cost=850000, region="Ahmedabad", depot="Ahmedabad Depot", status="Available"),
        Vehicle(id="v-truck11", registration="GJ 01 CD 8871", registration_normalized="GJ01CD8871", name="Truck-11", vehicle_type="Truck", capacity_kg=5000, odometer_km=119340, acquisition_cost=2250000, region="Ahmedabad", depot="Ahmedabad Depot", status="On Trip"),
        Vehicle(id="v-mini03", registration="GJ 27 MN 2203", registration_normalized="GJ27MN2203", name="Mini-03", vehicle_type="Mini Truck", capacity_kg=1200, odometer_km=67830, acquisition_cost=1180000, region="Surat", depot="Surat Depot", status="In Shop"),
        Vehicle(id="v-car02", registration="GJ 01 EF 4132", registration_normalized="GJ01EF4132", name="Car-02", vehicle_type="Car", capacity_kg=300, odometer_km=91500, acquisition_cost=620000, region="Ahmedabad", depot="Ahmedabad Depot", status="Retired"),
    ]
    drivers = [
        Driver(id="d-alex", name="Alex Thomas", license_number="GJ-DRV-1088", license_normalized="GJ-DRV-1088", license_category="LMV", license_expiry=date(2027, 10, 14), contact="+91 98765 32010", safety_score=94, status="Available", region="Ahmedabad", depot="Ahmedabad Depot"),
        Driver(id="d-rahul", name="Rahul Patel", license_number="GJ-DRV-1205", license_normalized="GJ-DRV-1205", license_category="HMV", license_expiry=date(2027, 3, 22), contact="+91 98765 10222", safety_score=88, status="On Trip", region="Ahmedabad", depot="Ahmedabad Depot"),
        Driver(id="d-neha", name="Neha Desai", license_number="GJ-DRV-1779", license_normalized="GJ-DRV-1779", license_category="LMV", license_expiry=date(2025, 12, 8), contact="+91 98765 76111", safety_score=91, status="Off Duty", region="Surat", depot="Surat Depot"),
        Driver(id="d-samir", name="Samir Khan", license_number="GJ-DRV-1882", license_normalized="GJ-DRV-1882", license_category="HMV", license_expiry=date(2027, 6, 1), contact="+91 98765 45789", safety_score=72, status="Suspended", region="Ahmedabad", depot="Ahmedabad Depot"),
    ]
    trips = [
        Trip(id="TR-1042", source="Ahmedabad Depot", destination="Vadodara Hub", source_latitude=23.0225, source_longitude=72.5714, destination_latitude=22.3072, destination_longitude=73.1812, vehicle_id="v-truck11", driver_id="d-rahul", cargo_kg=3200, planned_distance_km=112, revenue=18500, notes="Priority retail replenishment", status="Dispatched", created_at=datetime(2026, 7, 12, 8, 15)),
        Trip(id="TR-1043", source="Ahmedabad Depot", destination="Gandhinagar", source_latitude=23.0225, source_longitude=72.5714, destination_latitude=23.2156, destination_longitude=72.6369, vehicle_id="v-van05", driver_id="d-alex", cargo_kg=420, planned_distance_km=38, revenue=7200, notes="Draft delivery plan", status="Draft", created_at=datetime(2026, 7, 12, 9, 10)),
        Trip(id="TR-1039", source="Surat", destination="Bharuch", source_latitude=21.1702, source_longitude=72.8311, destination_latitude=21.7051, destination_longitude=72.9959, vehicle_id="v-mini03", driver_id="d-neha", cargo_kg=700, planned_distance_km=78, actual_distance_km=81, revenue=12400, notes="Completed before workshop booking", status="Completed", created_at=datetime(2026, 7, 10, 7), completed_at=datetime(2026, 7, 10, 12, 30)),
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
    session.add_all(roles)
    await session.flush()
    session.add_all([*users, *vehicles, *drivers])
    await session.flush()
    session.add_all([*trips, *maintenance])
    await session.flush()
    session.add_all([*fuel_logs, *expenses, Preference(
        id=1,
        depot_name="Ahmedabad Depot",
        currency="INR",
        distance_unit="Kilometres",
        map_provider=os.getenv("MAP_PROVIDER", "openstreetmap"),
        directions_provider=os.getenv("DIRECTIONS_PROVIDER", "straight_line"),
    )])
    await session.flush()


async def seed_tracking_data(session: AsyncSession) -> None:
    if not await session.get(Role, "role-driver"):
        session.add(Role(id="role-driver", name="Driver"))
        await session.flush()

    for user_id, region in (("u-fleet", "Ahmedabad"), ("u-dispatch", "Ahmedabad"), ("u-safety", "Ahmedabad"), ("u-finance", "Ahmedabad")):
        existing_user = await session.get(User, user_id)
        if existing_user and not existing_user.region:
            existing_user.region = region

    extra_vehicles = [
        Vehicle(id="v-van12", registration="GJ 01 GH 5412", registration_normalized="GJ01GH5412", name="Van-12", vehicle_type="Van", capacity_kg=650, odometer_km=31120, acquisition_cost=910000, region="Ahmedabad", depot="Ahmedabad Depot", status="On Trip"),
        Vehicle(id="v-truck15", registration="GJ 05 JK 7715", registration_normalized="GJ05JK7715", name="Truck-15", vehicle_type="Truck", capacity_kg=4200, odometer_km=88200, acquisition_cost=2100000, region="Ahmedabad", depot="Ahmedabad Depot", status="On Trip"),
    ]
    extra_drivers = [
        Driver(id="d-meera", name="Meera Joshi", license_number="GJ-DRV-2051", license_normalized="GJ-DRV-2051", license_category="LMV", license_expiry=date(2028, 4, 10), contact="+91 98765 88001", safety_score=96, status="On Trip", region="Ahmedabad", depot="Ahmedabad Depot"),
        Driver(id="d-vikram", name="Vikram Singh", license_number="GJ-DRV-2144", license_normalized="GJ-DRV-2144", license_category="HMV", license_expiry=date(2028, 1, 19), contact="+91 98765 88002", safety_score=89, status="On Trip", region="Ahmedabad", depot="Ahmedabad Depot"),
    ]
    for value in [*extra_vehicles, *extra_drivers]:
        if not await session.get(type(value), value.id):
            session.add(value)
    await session.flush()

    trips = [
        Trip(id="TR-1050", source="Ahmedabad Depot", destination="Sanand Warehouse", source_latitude=23.0225, source_longitude=72.5714, destination_latitude=22.9924, destination_longitude=72.3815, vehicle_id="v-van12", driver_id="d-meera", cargo_kg=480, planned_distance_km=31, revenue=6900, notes="Live tracking demo: stopped vehicle", status="In Progress", created_at=utc_now() - timedelta(hours=1)),
        Trip(id="TR-1051", source="Ahmedabad Depot", destination="Nadiad Customer", source_latitude=23.0225, source_longitude=72.5714, destination_latitude=22.6916, destination_longitude=72.8634, vehicle_id="v-truck15", driver_id="d-vikram", cargo_kg=2500, planned_distance_km=67, revenue=12200, notes="Live tracking demo: offline vehicle", status="In Progress", created_at=utc_now() - timedelta(hours=2)),
    ]
    for trip in trips:
        if not await session.get(Trip, trip.id):
            session.add(trip)
    core_trip = await session.get(Trip, "TR-1042")
    if core_trip:
        core_trip.source_latitude, core_trip.source_longitude = 23.0225, 72.5714
        core_trip.destination_latitude, core_trip.destination_longitude = 22.3072, 73.1812
    await session.flush()

    if not await session.scalar(select(User.id).where(User.email == "driver@transitops.demo")):
        password_hash = password_context.hash("demo")
        session.add_all([
            User(id="u-driver-rahul", name="Rahul Patel", email="driver@transitops.demo", password_hash=password_hash, role_id="role-driver", driver_id="d-rahul", region="Ahmedabad"),
            User(id="u-driver-meera", name="Meera Joshi", email="driver.meera@transitops.demo", password_hash=password_hash, role_id="role-driver", driver_id="d-meera", region="Ahmedabad"),
            User(id="u-driver-vikram", name="Vikram Singh", email="driver.vikram@transitops.demo", password_hash=password_hash, role_id="role-driver", driver_id="d-vikram", region="Ahmedabad"),
        ])
        await session.flush()

    now = utc_now()
    session_specs = [
        ("track-demo-rahul", "u-driver-rahul", "d-rahul", "v-truck11", "TR-1042", now - timedelta(minutes=45), 22.3260, 73.1600, 12.5, now - timedelta(seconds=8)),
        ("track-demo-meera", "u-driver-meera", "d-meera", "v-van12", "TR-1050", now - timedelta(minutes=35), 23.0040, 72.4400, 0.0, now - timedelta(seconds=75)),
        ("track-demo-vikram", "u-driver-vikram", "d-vikram", "v-truck15", "TR-1051", now - timedelta(hours=1), 22.8250, 72.7200, 7.2, now - timedelta(minutes=8)),
    ]
    for session_id, user_id, driver_id, vehicle_id, trip_id, started_at, latitude, longitude, speed, received_at in session_specs:
        tracking_session = await session.get(DriverTrackingSession, session_id)
        if not tracking_session:
            tracking_session = DriverTrackingSession(id=session_id, driver_id=driver_id, vehicle_id=vehicle_id, trip_id=trip_id, started_by_user_id=user_id, started_at=started_at, status="ACTIVE", consent_recorded_at=started_at, consent_version="2026-07", start_reason="DEMO_SEED", last_location_at=received_at, created_at=started_at, updated_at=received_at)
            session.add(tracking_session)
            await session.flush()
        point_id = f"loc-demo-{vehicle_id}"
        if not await session.get(VehicleLocationPoint, point_id):
            session.add(VehicleLocationPoint(id=point_id, tracking_session_id=session_id, driver_id=driver_id, vehicle_id=vehicle_id, trip_id=trip_id, latitude=latitude, longitude=longitude, accuracy_meters=12, heading_degrees=85, speed_mps=speed, captured_at=received_at, received_at=received_at, source="DRIVER_PHONE", idempotency_key=f"seed-{vehicle_id}", is_mock_location=True, location_metadata={"demo": True}))
        latest = await session.get(LatestVehicleLocation, vehicle_id)
        if not latest:
            session.add(LatestVehicleLocation(vehicle_id=vehicle_id, trip_id=trip_id, driver_id=driver_id, tracking_session_id=session_id, latitude=latitude, longitude=longitude, speed_mps=speed, heading_degrees=85, accuracy_meters=12, captured_at=received_at, received_at=received_at, freshness_status="ONLINE"))
    await session.flush()

    for fence in [
        Geofence(id="geo-ahmedabad-depot", depot_id="Ahmedabad Depot", name="Ahmedabad Depot", type="DEPOT", center_latitude=23.0225, center_longitude=72.5714, radius_meters=700, is_active=True, created_by="u-fleet", created_at=now, updated_at=now),
        Geofence(id="geo-vadodara-hub", depot_id="Ahmedabad Depot", name="Vadodara Hub", type="CUSTOMER", center_latitude=22.3072, center_longitude=73.1812, radius_meters=1000, is_active=True, created_by="u-fleet", created_at=now, updated_at=now),
    ]:
        if not await session.get(Geofence, fence.id):
            session.add(fence)
