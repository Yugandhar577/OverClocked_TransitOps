from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from typing import Annotated, Any, Literal, TypeVar
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import SessionLocal, engine, get_session
from .models import AuditEvent, Driver, Expense, FuelLog, Maintenance, Preference, Trip, User, Vehicle
from .seed import password_context, seed_demo_data


VehicleStatus = Literal["Available", "On Trip", "In Shop", "Retired"]
DriverStatus = Literal["Available", "On Trip", "Off Duty", "Suspended"]
RoleName = Literal["Fleet Manager", "Dispatcher", "Safety Officer", "Financial Analyst", "Administrator"]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class VehicleInput(BaseModel):
    registration: str = Field(min_length=3, max_length=32)
    name: str = Field(min_length=2, max_length=80)
    vehicle_type: str = Field(min_length=2, max_length=40)
    capacity_kg: float = Field(ge=0)
    odometer_km: float = Field(ge=0)
    acquisition_cost: float = Field(ge=0)
    region: str = "Ahmedabad"
    status: VehicleStatus = "Available"


class DriverInput(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    license_number: str = Field(min_length=3, max_length=32)
    license_category: str = "LMV"
    license_expiry: date
    contact: str = Field(min_length=5, max_length=30)
    safety_score: float = Field(ge=0, le=100)
    status: DriverStatus = "Available"
    region: str = "Ahmedabad"


class TripInput(BaseModel):
    source: str = Field(min_length=2, max_length=80)
    destination: str = Field(min_length=2, max_length=80)
    vehicle_id: str
    driver_id: str
    cargo_kg: float = Field(gt=0)
    planned_distance_km: float = Field(gt=0)
    revenue: float = Field(default=0, ge=0)
    notes: str = Field(default="", max_length=500)


class MaintenanceInput(BaseModel):
    vehicle_id: str
    service_type: str = Field(min_length=2, max_length=80)
    cost: float = Field(ge=0)
    notes: str = Field(default="", max_length=500)


class FuelInput(BaseModel):
    vehicle_id: str
    liters: float = Field(gt=0)
    cost: float = Field(gt=0)
    price_per_liter: float | None = Field(default=None, gt=0)
    odometer_km: float = Field(ge=0)
    vendor: str = Field(default="", max_length=80)
    trip_id: str | None = None
    logged_at: date = Field(default_factory=date.today)
    receipt_image: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def derive_price_per_liter(self) -> "FuelInput":
        if self.price_per_liter is None:
            self.price_per_liter = round(self.cost / self.liters, 2)
        return self


class ExpenseInput(BaseModel):
    category: Literal["Toll", "Miscellaneous"]
    amount: float = Field(gt=0)
    vehicle_id: str | None = None
    trip_id: str | None = None
    notes: str = Field(default="", max_length=300)


class PreferencesInput(BaseModel):
    depot_name: str = Field(min_length=2, max_length=100)
    currency: str = Field(min_length=3, max_length=8)
    distance_unit: Literal["Kilometres", "Miles"]


Session = Annotated[AsyncSession, Depends(get_session)]


def normalise(value: str) -> str:
    return "".join(value.upper().split())


def user_value(user: User) -> dict[str, Any]:
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role.name}


def vehicle_value(vehicle: Vehicle) -> dict[str, Any]:
    return {"id": vehicle.id, "registration": vehicle.registration, "name": vehicle.name, "vehicle_type": vehicle.vehicle_type, "capacity_kg": vehicle.capacity_kg, "odometer_km": vehicle.odometer_km, "acquisition_cost": vehicle.acquisition_cost, "region": vehicle.region, "status": vehicle.status}


def driver_value(driver: Driver) -> dict[str, Any]:
    return {"id": driver.id, "name": driver.name, "license_number": driver.license_number, "license_category": driver.license_category, "license_expiry": driver.license_expiry.isoformat(), "contact": driver.contact, "safety_score": driver.safety_score, "status": driver.status, "region": driver.region}


def trip_value(trip: Trip) -> dict[str, Any]:
    return {"id": trip.id, "source": trip.source, "destination": trip.destination, "vehicle_id": trip.vehicle_id, "driver_id": trip.driver_id, "cargo_kg": trip.cargo_kg, "planned_distance_km": trip.planned_distance_km, "actual_distance_km": trip.actual_distance_km, "revenue": trip.revenue, "notes": trip.notes, "status": trip.status, "created_at": trip.created_at.isoformat(), "completed_at": trip.completed_at.isoformat() if trip.completed_at else None, "cancellation_reason": trip.cancellation_reason}


def maintenance_value(record: Maintenance) -> dict[str, Any]:
    return {"id": record.id, "vehicle_id": record.vehicle_id, "service_type": record.service_type, "cost": record.cost, "status": record.status, "opened_at": record.opened_at.isoformat(), "closed_at": record.closed_at.isoformat() if record.closed_at else None, "notes": record.notes}


async def decorated_trip(session: AsyncSession, trip: Trip) -> dict[str, Any]:
    vehicle = await require_record(session, Vehicle, trip.vehicle_id)
    driver = await require_record(session, Driver, trip.driver_id)
    return {**trip_value(trip), "vehicle": vehicle.name, "driver": driver.name}


async def decorated_maintenance(session: AsyncSession, record: Maintenance) -> dict[str, Any]:
    vehicle = await require_record(session, Vehicle, record.vehicle_id)
    return {**maintenance_value(record), "vehicle": vehicle.name}


ModelType = TypeVar("ModelType")


async def require_record(session: AsyncSession, model: type[ModelType], record_id: str) -> ModelType:
    record = await session.get(model, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found.")
    return record


async def locked_record(session: AsyncSession, model: type[ModelType], record_id: str) -> ModelType:
    record = await session.scalar(select(model).where(model.id == record_id).with_for_update())
    if not record:
        raise HTTPException(status_code=404, detail="Record not found.")
    return record


async def current_user(session: Session, authorization: str | None = Header(default=None)) -> User:
    if not authorization or not authorization.startswith("Bearer demo-"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in to continue.")
    user = await require_record(session, User, authorization.removeprefix("Bearer demo-"))
    if not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in to continue.")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require(user: User, *roles: RoleName) -> None:
    if user.role.name not in roles:
        raise HTTPException(status_code=403, detail="Your role does not have permission for this action.")


async def audit(session: AsyncSession, user: User, event_type: str, target_type: str, target_id: str, before: dict[str, Any] | None, after: dict[str, Any] | None) -> None:
    session.add(AuditEvent(id=f"audit-{uuid4().hex[:12]}", actor_id=user.id, event_type=event_type, target_type=target_type, target_id=target_id, before_state=before, after_state=after))


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with SessionLocal.begin() as session:
        await seed_demo_data(session)
    try:
        yield
    finally:
        await engine.dispose()


from .routes.fuel_ocr_routes import router as fuel_ocr_router


app = FastAPI(title="TransitOps API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/uploads", StaticFiles(directory="app/uploads"), name="uploads")
app.include_router(fuel_ocr_router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/login")
async def login(payload: LoginRequest, session: Session) -> dict[str, Any]:
    user = await session.scalar(select(User).where(User.email == str(payload.email).lower()))
    if not user or not user.active or not password_context.verify(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return {"access_token": f"demo-{user.id}", "user": user_value(user)}


@app.get("/api/dashboard")
async def dashboard(user: CurrentUser, session: Session) -> dict[str, Any]:
    vehicles = list((await session.scalars(select(Vehicle))).all())
    trips = list((await session.scalars(select(Trip))).all())
    drivers = list((await session.scalars(select(Driver))).all())
    active_vehicles = [vehicle for vehicle in vehicles if vehicle.status != "Retired"]
    status_counts = {key: sum(vehicle.status == key for vehicle in vehicles) for key in ["Available", "On Trip", "In Shop", "Retired"]}
    recent = sorted(trips, key=lambda trip: trip.created_at, reverse=True)[:5]
    return {"kpis": {"activeVehicles": len(active_vehicles), "availableVehicles": status_counts["Available"], "inMaintenance": status_counts["In Shop"], "activeTrips": sum(trip.status == "Dispatched" for trip in trips), "pendingTrips": sum(trip.status == "Draft" for trip in trips), "driversOnDuty": sum(driver.status == "On Trip" for driver in drivers), "utilization": round(status_counts["On Trip"] / len(active_vehicles) * 100) if active_vehicles else 0}, "vehicleStatus": [{"name": key, "value": value} for key, value in status_counts.items()], "recentTrips": [await decorated_trip(session, trip) for trip in recent], "viewer": user_value(user)}


@app.get("/api/vehicles")
async def list_vehicles(_: CurrentUser, session: Session) -> list[dict[str, Any]]:
    return [vehicle_value(vehicle) for vehicle in (await session.scalars(select(Vehicle).order_by(Vehicle.name))).all()]


@app.post("/api/vehicles", status_code=201)
async def create_vehicle(payload: VehicleInput, user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Fleet Manager", "Administrator")
    normalized = normalise(payload.registration)
    if await session.scalar(select(Vehicle.id).where(Vehicle.registration_normalized == normalized)):
        raise HTTPException(status_code=409, detail="A vehicle with this registration already exists.")
    vehicle = Vehicle(id=f"v-{uuid4().hex[:8]}", registration_normalized=normalized, **payload.model_dump())
    session.add(vehicle)
    await audit(session, user, "vehicle.created", "vehicle", vehicle.id, None, vehicle_value(vehicle))
    return vehicle_value(vehicle)


@app.patch("/api/vehicles/{vehicle_id}")
async def update_vehicle(vehicle_id: str, payload: VehicleInput, user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Fleet Manager", "Administrator")
    vehicle = await locked_record(session, Vehicle, vehicle_id)
    if vehicle.status == "On Trip" and payload.status != "On Trip":
        raise HTTPException(status_code=409, detail="Complete or cancel the active trip before changing vehicle state.")
    normalized = normalise(payload.registration)
    duplicate = await session.scalar(select(Vehicle.id).where(Vehicle.registration_normalized == normalized, Vehicle.id != vehicle_id))
    if duplicate:
        raise HTTPException(status_code=409, detail="A vehicle with this registration already exists.")
    before = vehicle_value(vehicle)
    for field, value in payload.model_dump().items():
        setattr(vehicle, field, value)
    vehicle.registration_normalized = normalized
    await audit(session, user, "vehicle.updated", "vehicle", vehicle.id, before, vehicle_value(vehicle))
    return vehicle_value(vehicle)


@app.post("/api/vehicles/{vehicle_id}/retire")
async def retire_vehicle(vehicle_id: str, user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Fleet Manager", "Administrator")
    vehicle = await locked_record(session, Vehicle, vehicle_id)
    if vehicle.status == "On Trip":
        raise HTTPException(status_code=409, detail="Complete or cancel the active trip before retiring this vehicle.")
    active = await session.scalar(select(Maintenance.id).where(Maintenance.vehicle_id == vehicle_id, Maintenance.status == "Active").limit(1))
    if active:
        raise HTTPException(status_code=409, detail="Close active maintenance before retiring this vehicle.")
    before = vehicle_value(vehicle)
    vehicle.status = "Retired"
    await audit(session, user, "vehicle.retired", "vehicle", vehicle.id, before, vehicle_value(vehicle))
    return vehicle_value(vehicle)


@app.get("/api/drivers")
async def list_drivers(_: CurrentUser, session: Session) -> list[dict[str, Any]]:
    return [driver_value(driver) for driver in (await session.scalars(select(Driver).order_by(Driver.name))).all()]


@app.post("/api/drivers", status_code=201)
async def create_driver(payload: DriverInput, user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Fleet Manager", "Safety Officer", "Administrator")
    normalized = normalise(payload.license_number)
    if await session.scalar(select(Driver.id).where(Driver.license_normalized == normalized)):
        raise HTTPException(status_code=409, detail="A driver with this licence number already exists.")
    driver = Driver(id=f"d-{uuid4().hex[:8]}", license_normalized=normalized, **payload.model_dump())
    session.add(driver)
    await audit(session, user, "driver.created", "driver", driver.id, None, driver_value(driver))
    return driver_value(driver)


@app.patch("/api/drivers/{driver_id}")
async def update_driver(driver_id: str, payload: DriverInput, user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Fleet Manager", "Safety Officer", "Administrator")
    driver = await locked_record(session, Driver, driver_id)
    if driver.status == "On Trip" and payload.status != "On Trip":
        raise HTTPException(status_code=409, detail="Complete or cancel the active trip before changing driver state.")
    normalized = normalise(payload.license_number)
    duplicate = await session.scalar(select(Driver.id).where(Driver.license_normalized == normalized, Driver.id != driver_id))
    if duplicate:
        raise HTTPException(status_code=409, detail="A driver with this licence number already exists.")
    before = driver_value(driver)
    for field, value in payload.model_dump().items():
        setattr(driver, field, value)
    driver.license_normalized = normalized
    await audit(session, user, "driver.updated", "driver", driver.id, before, driver_value(driver))
    return driver_value(driver)


@app.get("/api/trips")
async def list_trips(_: CurrentUser, session: Session) -> list[dict[str, Any]]:
    trips = (await session.scalars(select(Trip).order_by(Trip.created_at.desc()))).all()
    return [await decorated_trip(session, trip) for trip in trips]


@app.post("/api/trips", status_code=201)
async def create_trip(payload: TripInput, user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Dispatcher", "Fleet Manager", "Administrator")
    vehicle = await require_record(session, Vehicle, payload.vehicle_id)
    await require_record(session, Driver, payload.driver_id)
    if payload.cargo_kg > vehicle.capacity_kg:
        raise HTTPException(status_code=422, detail=f"Cargo exceeds {vehicle.name} capacity by {payload.cargo_kg - vehicle.capacity_kg:.0f} kg.")
    trip = Trip(id=f"TR-{uuid4().hex[:8].upper()}", **payload.model_dump(), status="Draft", created_at=datetime.now(UTC).replace(tzinfo=None))
    session.add(trip)
    await audit(session, user, "trip.created", "trip", trip.id, None, trip_value(trip))
    return await decorated_trip(session, trip)


@app.post("/api/trips/{trip_id}/dispatch")
async def dispatch(trip_id: str, user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Dispatcher", "Fleet Manager", "Administrator")
    trip = await locked_record(session, Trip, trip_id)
    if trip.status != "Draft":
        raise HTTPException(status_code=409, detail="Only draft trips can be dispatched.")
    vehicle = await locked_record(session, Vehicle, trip.vehicle_id)
    driver = await locked_record(session, Driver, trip.driver_id)
    reasons: list[str] = []
    if vehicle.status != "Available": reasons.append(f"{vehicle.name} is {vehicle.status}.")
    if driver.status != "Available": reasons.append(f"{driver.name} is {driver.status}.")
    if driver.license_expiry < date.today(): reasons.append(f"{driver.name}'s licence is expired.")
    if trip.cargo_kg > vehicle.capacity_kg: reasons.append(f"Cargo exceeds capacity by {trip.cargo_kg - vehicle.capacity_kg:.0f} kg.")
    if reasons:
        raise HTTPException(status_code=409, detail=" ".join(reasons))
    before = trip_value(trip)
    trip.status, vehicle.status, driver.status = "Dispatched", "On Trip", "On Trip"
    await audit(session, user, "trip.dispatched", "trip", trip.id, before, trip_value(trip))
    return await decorated_trip(session, trip)


async def release_trip_resources(session: AsyncSession, trip: Trip) -> None:
    vehicle = await locked_record(session, Vehicle, trip.vehicle_id)
    driver = await locked_record(session, Driver, trip.driver_id)
    if vehicle.status == "On Trip": vehicle.status = "Available"
    if driver.status == "On Trip": driver.status = "Available"


@app.post("/api/trips/{trip_id}/complete")
async def complete(trip_id: str, user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Dispatcher", "Fleet Manager", "Administrator")
    trip = await locked_record(session, Trip, trip_id)
    if trip.status != "Dispatched":
        raise HTTPException(status_code=409, detail="Only dispatched trips can be completed.")
    before = trip_value(trip)
    trip.status, trip.completed_at = "Completed", datetime.now(UTC).replace(tzinfo=None)
    await release_trip_resources(session, trip)
    await audit(session, user, "trip.completed", "trip", trip.id, before, trip_value(trip))
    return await decorated_trip(session, trip)


@app.post("/api/trips/{trip_id}/cancel")
async def cancel(trip_id: str, user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Dispatcher", "Fleet Manager", "Administrator")
    trip = await locked_record(session, Trip, trip_id)
    if trip.status not in ("Draft", "Dispatched"):
        raise HTTPException(status_code=409, detail="Only draft or dispatched trips can be cancelled.")
    before = trip_value(trip)
    if trip.status == "Dispatched":
        await release_trip_resources(session, trip)
    trip.status, trip.cancellation_reason = "Cancelled", "Cancelled by dispatcher"
    await audit(session, user, "trip.cancelled", "trip", trip.id, before, trip_value(trip))
    return await decorated_trip(session, trip)


@app.get("/api/maintenance")
async def list_maintenance(_: CurrentUser, session: Session) -> list[dict[str, Any]]:
    records = (await session.scalars(select(Maintenance).order_by(Maintenance.opened_at.desc()))).all()
    return [await decorated_maintenance(session, record) for record in records]


@app.post("/api/maintenance", status_code=201)
async def create_maintenance(payload: MaintenanceInput, user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Fleet Manager", "Administrator")
    vehicle = await locked_record(session, Vehicle, payload.vehicle_id)
    if vehicle.status == "On Trip": raise HTTPException(status_code=409, detail="A vehicle on an active trip cannot enter maintenance.")
    if vehicle.status == "Retired": raise HTTPException(status_code=409, detail="A retired vehicle cannot enter maintenance.")
    active = await session.scalar(select(Maintenance.id).where(Maintenance.vehicle_id == vehicle.id, Maintenance.status == "Active").limit(1))
    if active: raise HTTPException(status_code=409, detail="This vehicle already has active maintenance.")
    record = Maintenance(id=f"m-{uuid4().hex[:8]}", **payload.model_dump(), status="Active", opened_at=date.today())
    session.add(record)
    vehicle.status = "In Shop"
    await audit(session, user, "maintenance.opened", "maintenance", record.id, None, maintenance_value(record))
    return await decorated_maintenance(session, record)


@app.post("/api/maintenance/{maintenance_id}/close")
async def close_maintenance(maintenance_id: str, user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Fleet Manager", "Administrator")
    record = await locked_record(session, Maintenance, maintenance_id)
    if record.status != "Active": raise HTTPException(status_code=409, detail="This maintenance record is already closed.")
    before = maintenance_value(record)
    record.status, record.closed_at = "Completed", date.today()
    vehicle = await locked_record(session, Vehicle, record.vehicle_id)
    active = await session.scalar(select(Maintenance.id).where(Maintenance.vehicle_id == vehicle.id, Maintenance.status == "Active", Maintenance.id != record.id).limit(1))
    if not active and vehicle.status != "Retired": vehicle.status = "Available"
    await audit(session, user, "maintenance.closed", "maintenance", record.id, before, maintenance_value(record))
    return await decorated_maintenance(session, record)


@app.get("/api/finance")
async def finance(_: CurrentUser, session: Session) -> dict[str, Any]:
    fuel_logs = (await session.scalars(select(FuelLog).order_by(FuelLog.logged_at.desc()))).all()
    expenses = (await session.scalars(select(Expense).order_by(Expense.logged_at.desc()))).all()
    maintenance = (await session.scalars(select(Maintenance))).all()
    vehicle_names = {vehicle.id: vehicle.name for vehicle in (await session.scalars(select(Vehicle))).all()}
    fuel_cost = sum(log.cost for log in fuel_logs)
    maintenance_cost = sum(record.cost for record in maintenance)
    return {"fuelLogs": [{"id": log.id, "vehicle_id": log.vehicle_id, "vehicle": vehicle_names[log.vehicle_id], "trip_id": log.trip_id, "date": log.logged_at.isoformat(), "liters": log.liters, "cost": log.cost, "price_per_liter": log.price_per_liter, "odometer_km": log.odometer_km, "vendor": log.vendor, "receipt_image": log.receipt_image} for log in fuel_logs], "expenses": [{"id": item.id, "category": item.category, "amount": item.amount, "vehicle_id": item.vehicle_id, "vehicle": vehicle_names.get(item.vehicle_id, "-"), "trip_id": item.trip_id, "date": item.logged_at.isoformat(), "notes": item.notes} for item in expenses], "operationalCost": fuel_cost + maintenance_cost, "expandedCost": fuel_cost + maintenance_cost + sum(item.amount for item in expenses)}


@app.post("/api/finance/fuel", status_code=201)
async def add_fuel(payload: FuelInput, user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Financial Analyst", "Fleet Manager", "Administrator")
    await require_record(session, Vehicle, payload.vehicle_id)
    if payload.trip_id: await require_record(session, Trip, payload.trip_id)
    record = FuelLog(id=f"f-{uuid4().hex[:8]}", **payload.model_dump())
    session.add(record)
    return {"id": record.id, **payload.model_dump(mode="json"), "date": record.logged_at.isoformat()}


@app.post("/api/finance/expenses", status_code=201)
async def add_expense(payload: ExpenseInput, user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Financial Analyst", "Fleet Manager", "Administrator")
    if payload.vehicle_id: await require_record(session, Vehicle, payload.vehicle_id)
    if payload.trip_id: await require_record(session, Trip, payload.trip_id)
    record = Expense(id=f"e-{uuid4().hex[:8]}", **payload.model_dump(), logged_at=date.today())
    session.add(record)
    return {"id": record.id, **payload.model_dump(), "date": record.logged_at.isoformat()}


@app.get("/api/analytics")
async def analytics(_: CurrentUser, session: Session) -> dict[str, Any]:
    fuel_logs = (await session.scalars(select(FuelLog))).all()
    maintenance = (await session.scalars(select(Maintenance))).all()
    trips = (await session.scalars(select(Trip))).all()
    vehicles = (await session.scalars(select(Vehicle))).all()
    fuel_cost, maintenance_cost = sum(item.cost for item in fuel_logs), sum(item.cost for item in maintenance)
    total_litres = sum(item.liters for item in fuel_logs)
    completed_distance = sum((trip.actual_distance_km or trip.planned_distance_km) for trip in trips if trip.status == "Completed")
    active_vehicles = [vehicle for vehicle in vehicles if vehicle.status != "Retired"]
    revenue = sum(trip.revenue for trip in trips if trip.status in ("Completed", "Dispatched"))
    acquisition_cost = sum(vehicle.acquisition_cost for vehicle in active_vehicles)
    costs = [{"vehicle": vehicle.name, "cost": sum(item.cost for item in fuel_logs if item.vehicle_id == vehicle.id) + sum(item.cost for item in maintenance if item.vehicle_id == vehicle.id)} for vehicle in vehicles]
    return {"metrics": {"fuelEfficiency": round(completed_distance / total_litres, 1) if total_litres else None, "utilization": round(sum(vehicle.status == "On Trip" for vehicle in active_vehicles) / len(active_vehicles) * 100) if active_vehicles else 0, "operationalCost": fuel_cost + maintenance_cost, "roi": round((revenue - fuel_cost - maintenance_cost) / acquisition_cost * 100, 1) if acquisition_cost else None}, "revenue": [{"month": "Apr", "amount": 16200}, {"month": "May", "amount": 22400}, {"month": "Jun", "amount": 19500}, {"month": "Jul", "amount": revenue}], "costliestVehicles": sorted(costs, key=lambda item: item["cost"], reverse=True)}


@app.get("/api/analytics/export")
async def export_analytics(user: CurrentUser, session: Session) -> Response:
    require(user, "Fleet Manager", "Financial Analyst", "Administrator")
    fuel_logs = (await session.scalars(select(FuelLog))).all()
    maintenance = (await session.scalars(select(Maintenance))).all()
    vehicles = (await session.scalars(select(Vehicle))).all()
    rows = ["vehicle,operational_cost", *[f'"{vehicle.name}",{sum(item.cost for item in fuel_logs if item.vehicle_id == vehicle.id) + sum(item.cost for item in maintenance if item.vehicle_id == vehicle.id):.2f}' for vehicle in vehicles]]
    return Response("\n".join(rows) + "\n", media_type="text/csv", headers={"Content-Disposition": "attachment; filename=transitops-analytics.csv"})


@app.get("/api/settings")
async def get_settings(user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Fleet Manager", "Administrator")
    preferences = await require_record(session, Preference, 1)
    return {"depot_name": preferences.depot_name, "currency": preferences.currency, "distance_unit": preferences.distance_unit}


@app.put("/api/settings")
async def update_settings(payload: PreferencesInput, user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Fleet Manager", "Administrator")
    preferences = await require_record(session, Preference, 1)
    before = {"depot_name": preferences.depot_name, "currency": preferences.currency, "distance_unit": preferences.distance_unit}
    for field, value in payload.model_dump().items(): setattr(preferences, field, value)
    after = {"depot_name": preferences.depot_name, "currency": preferences.currency, "distance_unit": preferences.distance_unit}
    await audit(session, user, "preferences.updated", "preferences", "1", before, after)
    return after
