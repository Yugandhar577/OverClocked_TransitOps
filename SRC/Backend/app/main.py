from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
import os
from typing import Annotated, Any, Literal, TypeVar
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import SessionLocal, engine, get_session
from .dashboard import RESOURCE_PERMISSION, can, compose_dashboard, permissions_for
from .models import AuditEvent, Driver, Expense, FuelLog, Maintenance, OdometerLog, Preference, Trip, User, Vehicle, VehicleDocument
from .seed import password_context, seed_demo_data
from .tracking import cleanup_expired_locations, end_tracking_for_driver, end_tracking_for_trip, router as tracking_router


VehicleStatus = Literal["Available", "On Trip", "In Shop", "Retired"]
DriverStatus = Literal["Available", "On Trip", "Off Duty", "Suspended"]
RoleName = Literal["Fleet Manager", "Dispatcher", "Safety Officer", "Financial Analyst", "Administrator", "Driver"]
JWT_SECRET = os.getenv("TRANSITOPS_JWT_SECRET", "transitops-local-demo-secret-change-in-production")
JWT_ALGORITHM = "HS256"
TOKEN_TTL_HOURS = 8
failed_logins: dict[str, list[datetime]] = {}
revoked_tokens: dict[str, datetime] = {}
MaintenanceStatus = Literal["Scheduled", "In Progress", "Completed", "Cancelled"]
MaintenancePriority = Literal["Low", "Normal", "Urgent"]
FuelType = Literal["Diesel", "Petrol", "CNG", "Electric", "Hybrid"]
DocumentType = Literal["Insurance", "PUC", "Fitness Certificate", "Permit", "Road Tax", "Lease"]


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
    brand: str = Field(default="", max_length=60)
    model: str = Field(default="", max_length=60)
    vin: str = Field(default="", max_length=64)
    fuel_type: FuelType = "Diesel"
    manufacture_year: int | None = Field(default=None, ge=1900, le=2100)
    color: str = Field(default="", max_length=40)
    photo_url: str = Field(default="", max_length=2_000_000)


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
    source_latitude: float | None = Field(default=None, ge=-90, le=90)
    source_longitude: float | None = Field(default=None, ge=-180, le=180)
    destination_latitude: float | None = Field(default=None, ge=-90, le=90)
    destination_longitude: float | None = Field(default=None, ge=-180, le=180)
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
    vendor: str = Field(default="", max_length=80)
    odometer_km: float | None = Field(default=None, ge=0)
    invoice_reference: str = Field(default="", max_length=80)
    priority: MaintenancePriority = "Normal"
    due_date: date | None = None
    status: MaintenanceStatus = "In Progress"


class OdometerInput(BaseModel):
    value_km: float = Field(ge=0)
    logged_at: date | None = None


class TripCompletionInput(BaseModel):
    actual_distance_km: float | None = Field(default=None, gt=0)
    odometer_km: float | None = Field(default=None, ge=0)


class VehicleDocumentInput(BaseModel):
    document_type: DocumentType
    reference_number: str = Field(default="", max_length=80)
    provider: str = Field(default="", max_length=100)
    start_date: date
    expiry_date: date
    cost: float = Field(default=0, ge=0)


class VehicleDocumentRenewInput(VehicleDocumentInput):
    document_type: DocumentType | None = None


class FuelInput(BaseModel):
    vehicle_id: str
    liters: float = Field(gt=0)
    cost: float = Field(gt=0)
    odometer_km: float = Field(ge=0)
    vendor: str = Field(default="", max_length=80)
    trip_id: str | None = None


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
    live_tracking_enabled: bool = True
    tracking_update_interval_seconds: int = Field(default=10, ge=5, le=120)
    tracking_stationary_interval_seconds: int = Field(default=25, ge=10, le=300)
    tracking_minimum_movement_meters: float = Field(default=20, ge=1, le=1000)
    tracking_stale_seconds: int = Field(default=60, ge=15, le=3600)
    tracking_offline_seconds: int = Field(default=180, ge=30, le=86400)
    tracking_raw_retention_days: int = Field(default=60, ge=1, le=3650)
    driver_fleet_visibility: Literal["OWN_VEHICLE_ONLY", "SAME_TRIP_GROUP", "SAME_DEPOT_ACTIVE_VEHICLES", "ALL_AUTHORIZED_ACTIVE_VEHICLES"] = "OWN_VEHICLE_ONLY"
    allow_driver_pause: bool = True
    allow_driver_nearby_vehicles: bool = False
    map_provider: Literal["openstreetmap", "mapbox", "google"] = "openstreetmap"
    directions_provider: Literal["straight_line", "openrouteservice", "mapbox", "google"] = "straight_line"
    geofence_alerts_enabled: bool = True
    license_expiry_warning_days: int = Field(default=30, ge=7, le=180)
    license_expiry_critical_days: int = Field(default=7, ge=1, le=30)

    @model_validator(mode="after")
    def validate_expiry_windows(self) -> "PreferencesInput":
        if self.license_expiry_critical_days > self.license_expiry_warning_days:
            raise ValueError("The critical licence window cannot exceed the warning window.")
        return self


Session = Annotated[AsyncSession, Depends(get_session)]


def normalise(value: str) -> str:
    return "".join(value.upper().split())


def user_value(user: User) -> dict[str, Any]:
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role.name, "driver_id": user.driver_id, "region": user.region}


def vehicle_value(vehicle: Vehicle) -> dict[str, Any]:
    return {
        "id": vehicle.id, "registration": vehicle.registration, "name": vehicle.name,
        "vehicle_type": vehicle.vehicle_type, "capacity_kg": vehicle.capacity_kg,
        "odometer_km": vehicle.odometer_km, "acquisition_cost": vehicle.acquisition_cost,
        "region": vehicle.region, "depot": vehicle.depot, "status": vehicle.status, "brand": vehicle.brand,
        "model": vehicle.model, "vin": vehicle.vin, "fuel_type": vehicle.fuel_type,
        "manufacture_year": vehicle.manufacture_year, "color": vehicle.color,
        "photo_url": vehicle.photo_url,
    }


def driver_value(driver: Driver) -> dict[str, Any]:
    return {"id": driver.id, "name": driver.name, "license_number": driver.license_number, "license_category": driver.license_category, "license_expiry": driver.license_expiry.isoformat(), "contact": driver.contact, "safety_score": driver.safety_score, "status": driver.status, "region": driver.region, "depot": driver.depot}


def trip_value(trip: Trip) -> dict[str, Any]:
    return {"id": trip.id, "source": trip.source, "destination": trip.destination, "source_latitude": trip.source_latitude, "source_longitude": trip.source_longitude, "destination_latitude": trip.destination_latitude, "destination_longitude": trip.destination_longitude, "vehicle_id": trip.vehicle_id, "driver_id": trip.driver_id, "cargo_kg": trip.cargo_kg, "planned_distance_km": trip.planned_distance_km, "actual_distance_km": trip.actual_distance_km, "revenue": trip.revenue, "notes": trip.notes, "status": trip.status, "created_at": trip.created_at.isoformat(), "completed_at": trip.completed_at.isoformat() if trip.completed_at else None, "cancellation_reason": trip.cancellation_reason}


def maintenance_value(record: Maintenance) -> dict[str, Any]:
    return {
        "id": record.id, "vehicle_id": record.vehicle_id, "service_type": record.service_type,
        "cost": record.cost, "status": record.status, "opened_at": record.opened_at.isoformat(),
        "closed_at": record.closed_at.isoformat() if record.closed_at else None, "notes": record.notes,
        "vendor": record.vendor, "odometer_km": record.odometer_km,
        "invoice_reference": record.invoice_reference, "priority": record.priority,
        "due_date": record.due_date.isoformat() if record.due_date else None,
        "downtime_days": ((record.closed_at or date.today()) - record.opened_at).days if record.status == "In Progress" or record.closed_at else 0,
    }


def document_status(document: VehicleDocument) -> str:
    if document.status == "Renewed":
        return "Renewed"
    if document.expiry_date < date.today():
        return "Expired"
    if document.expiry_date <= date.today() + timedelta(days=30):
        return "Expiring Soon"
    return "Active"


def document_value(document: VehicleDocument) -> dict[str, Any]:
    return {
        "id": document.id, "vehicle_id": document.vehicle_id, "document_type": document.document_type,
        "reference_number": document.reference_number, "provider": document.provider,
        "start_date": document.start_date.isoformat(), "expiry_date": document.expiry_date.isoformat(),
        "cost": document.cost, "status": document_status(document),
    }


async def add_odometer_log(session: AsyncSession, vehicle: Vehicle, value_km: float, source: str, driver_id: str | None = None, logged_at: date | None = None) -> OdometerLog:
    log = OdometerLog(
        id=f"odo-{uuid4().hex[:10]}", vehicle_id=vehicle.id, value_km=value_km,
        source=source, driver_id=driver_id, logged_at=logged_at or date.today(),
    )
    session.add(log)
    vehicle.odometer_km = value_km
    return log


async def decorated_trip(session: AsyncSession, trip: Trip) -> dict[str, Any]:
    vehicle = await require_record(session, Vehicle, trip.vehicle_id)
    driver = await require_record(session, Driver, trip.driver_id)
    return {**trip_value(trip), "vehicle": vehicle.name, "driver": driver.name}


async def decorated_maintenance(session: AsyncSession, record: Maintenance) -> dict[str, Any]:
    vehicle = await require_record(session, Vehicle, record.vehicle_id)
    return {**maintenance_value(record), "vehicle": vehicle.name}


async def collect_alerts(session: AsyncSession) -> list[dict[str, str]]:
    today = date.today()
    preferences = await session.get(Preference, 1)
    warning_days = preferences.license_expiry_warning_days if preferences else 30
    critical_days = preferences.license_expiry_critical_days if preferences else 7
    alert_items: list[dict[str, str]] = []
    drivers = (await session.scalars(select(Driver))).all()
    vehicles = {vehicle.id: vehicle for vehicle in (await session.scalars(select(Vehicle))).all()}
    documents = (await session.scalars(select(VehicleDocument).where(VehicleDocument.status != "Renewed"))).all()
    maintenance = (await session.scalars(select(Maintenance).where(Maintenance.status.in_(["Scheduled", "In Progress"])))) .all()

    for driver in drivers:
        if driver.license_expiry < today:
            alert_items.append({"severity": "critical", "message": f"{driver.name}'s licence expired on {driver.license_expiry:%d %b %Y}.", "entity_type": "driver", "entity_id": driver.id, "link": f"/drivers/{driver.id}"})
        elif driver.license_expiry <= today + timedelta(days=warning_days):
            alert_items.append({"severity": "critical" if driver.license_expiry <= today + timedelta(days=critical_days) else "warning", "message": f"{driver.name}'s licence expires on {driver.license_expiry:%d %b %Y}.", "entity_type": "driver", "entity_id": driver.id, "link": f"/drivers/{driver.id}"})
    for document in documents:
        vehicle = vehicles[document.vehicle_id]
        if document.expiry_date < today:
            alert_items.append({"severity": "critical", "message": f"{vehicle.name} {document.document_type} expired on {document.expiry_date:%d %b %Y}.", "entity_type": "vehicle", "entity_id": vehicle.id, "link": f"/fleet/{vehicle.id}"})
        elif document.expiry_date <= today + timedelta(days=30):
            alert_items.append({"severity": "warning", "message": f"{vehicle.name} {document.document_type} expires on {document.expiry_date:%d %b %Y}.", "entity_type": "vehicle", "entity_id": vehicle.id, "link": f"/fleet/{vehicle.id}"})
    for record in maintenance:
        vehicle = vehicles[record.vehicle_id]
        if record.priority == "Urgent":
            alert_items.append({"severity": "critical", "message": f"Urgent maintenance: {vehicle.name} — {record.service_type} ({record.status}).", "entity_type": "maintenance", "entity_id": record.id, "link": f"/fleet/{vehicle.id}"})
        if record.status == "In Progress" and record.opened_at < today - timedelta(days=7):
            alert_items.append({"severity": "critical", "message": f"{vehicle.name} has been In Shop for {(today - record.opened_at).days} days.", "entity_type": "maintenance", "entity_id": record.id, "link": f"/fleet/{vehicle.id}"})
    return sorted(alert_items, key=lambda item: (item["severity"] != "critical", item["message"]))


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
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in to continue.")
    token = authorization.removeprefix("Bearer ")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        token_id = payload.get("jti")
        user_id = payload.get("sub")
        if not token_id or not user_id or token_id in revoked_tokens:
            raise JWTError("Invalid session")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your session is invalid or expired. Please sign in again.")
    user = await require_record(session, User, user_id)
    if not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in to continue.")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require(user: User, *roles: RoleName) -> None:
    if user.role.name not in roles:
        raise HTTPException(status_code=403, detail="Your role does not have permission for this action.")


def require_permission(user: User, resource: str) -> None:
    if not can(user, RESOURCE_PERMISSION[resource]):
        raise HTTPException(status_code=403, detail="Your role does not have permission to read this resource.")


async def audit(session: AsyncSession, user: User, event_type: str, target_type: str, target_id: str, before: dict[str, Any] | None, after: dict[str, Any] | None) -> None:
    session.add(AuditEvent(id=f"audit-{uuid4().hex[:12]}", actor_id=user.id, event_type=event_type, target_type=target_type, target_id=target_id, before_state=before, after_state=after))


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with SessionLocal.begin() as session:
        await seed_demo_data(session)
        await cleanup_expired_locations(session)
    try:
        yield
    finally:
        await engine.dispose()


app = FastAPI(title="TransitOps API", version="0.2.0", lifespan=lifespan)
frontend_origins = [value.strip() for value in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if value.strip()]
app.add_middleware(CORSMiddleware, allow_origins=frontend_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(tracking_router)


@app.middleware("http")
async def tracking_request_guards(request: Request, call_next):
    if request.url.path.startswith("/api/tracking"):
        content_length = int(request.headers.get("content-length", "0") or 0)
        if content_length > 262_144:
            return Response(status_code=413, content="Tracking payload is too large.")
        if os.getenv("ENVIRONMENT", "development") == "production" and request.headers.get("x-forwarded-proto", request.url.scheme) != "https":
            return Response(status_code=400, content="HTTPS is required for live tracking.")
    return await call_next(request)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/login")
async def login(payload: LoginRequest, session: Session) -> dict[str, Any]:
    now = datetime.now(UTC)
    email = str(payload.email).lower()
    attempts = [item for item in failed_logins.get(email, []) if now - item < timedelta(minutes=15)]
    if len(attempts) >= 5:
        raise HTTPException(status_code=429, detail="Too many failed sign-in attempts. Try again in 15 minutes.")
    user = await session.scalar(select(User).where(User.email == email))
    if not user or not user.active or not password_context.verify(payload.password, user.password_hash):
        failed_logins[email] = [*attempts, now]
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    failed_logins.pop(email, None)
    token_id = uuid4().hex
    revoked_tokens.update({key: expiry for key, expiry in revoked_tokens.items() if expiry > now})
    token = jwt.encode({"sub": user.id, "jti": token_id, "exp": now + timedelta(hours=TOKEN_TTL_HOURS)}, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {"access_token": token, "user": user_value(user)}


@app.post("/api/auth/logout", status_code=204, response_class=Response)
async def logout(user: CurrentUser, session: Session, authorization: str | None = Header(default=None)) -> Response:
    token = authorization.removeprefix("Bearer ") if authorization else ""
    try:
        token_id = jwt.get_unverified_claims(token).get("jti")
        expiry = datetime.fromtimestamp(jwt.get_unverified_claims(token).get("exp"), UTC)
        if token_id:
            revoked_tokens[token_id] = expiry
    except (JWTError, TypeError, ValueError):
        pass
    if user.driver_id:
        await end_tracking_for_driver(session, user.driver_id, "DRIVER_LOGOUT", user.id)
    return Response(status_code=204)


@app.get("/api/dashboard")
async def dashboard(user: CurrentUser, session: Session, region: str | None = Query(default=None, min_length=2, max_length=80), vehicle_type: str | None = Query(default=None, min_length=2, max_length=80)) -> dict[str, Any]:
    try:
        return await compose_dashboard(session, user, region, vehicle_type)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error


@app.get("/api/auth/permissions")
async def permission_summary(user: CurrentUser) -> dict[str, Any]:
    return {"role": user.role.name, "permissions": sorted(permissions_for(user))}


@app.get("/api/alerts")
async def alerts(user: CurrentUser, session: Session) -> dict[str, Any]:
    require_permission(user, "alerts")
    active_alerts = await collect_alerts(session)
    if user.role.name == "Safety Officer":
        active_alerts = [item for item in active_alerts if item["entity_type"] == "driver"]
    elif user.role.name == "Fleet Manager":
        active_alerts = [item for item in active_alerts if item["entity_type"] in {"vehicle", "maintenance"}]
    elif user.role.name in {"Dispatcher", "Financial Analyst", "Driver"}:
        active_alerts = []
    return {"alerts": active_alerts, "critical_count": sum(item["severity"] == "critical" for item in active_alerts)}


@app.get("/api/vehicles")
async def list_vehicles(user: CurrentUser, session: Session) -> list[dict[str, Any]]:
    require_permission(user, "vehicles")
    return [vehicle_value(vehicle) for vehicle in (await session.scalars(select(Vehicle).order_by(Vehicle.name))).all()]


@app.get("/api/vehicles/{vehicle_id}")
async def vehicle_detail(vehicle_id: str, user: CurrentUser, session: Session) -> dict[str, Any]:
    require_permission(user, "vehicles")
    vehicle = await require_record(session, Vehicle, vehicle_id)
    current_trip = await session.scalar(select(Trip).where(Trip.vehicle_id == vehicle.id, Trip.status == "Dispatched").order_by(Trip.created_at.desc()))
    assigned_driver = await require_record(session, Driver, current_trip.driver_id) if current_trip else None
    logs = (await session.scalars(select(OdometerLog).where(OdometerLog.vehicle_id == vehicle.id).order_by(OdometerLog.logged_at.desc(), OdometerLog.id.desc()))).all()
    driver_names = {driver.id: driver.name for driver in (await session.scalars(select(Driver))).all()}
    documents = (await session.scalars(select(VehicleDocument).where(VehicleDocument.vehicle_id == vehicle.id).order_by(VehicleDocument.expiry_date))).all()
    maintenance = (await session.scalars(select(Maintenance).where(Maintenance.vehicle_id == vehicle.id).order_by(Maintenance.opened_at.desc()))).all()
    fuel_cost = await session.scalars(select(FuelLog).where(FuelLog.vehicle_id == vehicle.id))
    return {
        **vehicle_value(vehicle),
        "operational": {"assigned_driver": driver_value(assigned_driver) if assigned_driver else None, "current_trip": await decorated_trip(session, current_trip) if current_trip else None},
        "odometer_history": [{"id": log.id, "date": log.logged_at.isoformat(), "value_km": log.value_km, "source": log.source, "driver_id": log.driver_id, "driver": driver_names.get(log.driver_id)} for log in logs],
        "documents": [document_value(document) for document in documents],
        "maintenance_history": [await decorated_maintenance(session, record) for record in maintenance],
        "cost_summary": {"fuel": sum(log.cost for log in fuel_cost), "maintenance": sum(record.cost for record in maintenance), "documents": sum(document.cost for document in documents), "total": sum(log.cost for log in fuel_cost) + sum(record.cost for record in maintenance) + sum(document.cost for document in documents)},
    }


@app.post("/api/vehicles", status_code=201)
async def create_vehicle(payload: VehicleInput, user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Fleet Manager", "Administrator")
    normalized = normalise(payload.registration)
    if await session.scalar(select(Vehicle.id).where(Vehicle.registration_normalized == normalized)):
        raise HTTPException(status_code=409, detail="A vehicle with this registration already exists.")
    vehicle = Vehicle(id=f"v-{uuid4().hex[:8]}", registration_normalized=normalized, **payload.model_dump())
    session.add(vehicle)
    await add_odometer_log(session, vehicle, payload.odometer_km, "manual entry")
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
    odometer_changed = vehicle.odometer_km != payload.odometer_km
    for field, value in payload.model_dump().items():
        setattr(vehicle, field, value)
    vehicle.registration_normalized = normalized
    if odometer_changed:
        await add_odometer_log(session, vehicle, payload.odometer_km, "manual entry")
    await audit(session, user, "vehicle.updated", "vehicle", vehicle.id, before, vehicle_value(vehicle))
    return vehicle_value(vehicle)


@app.post("/api/vehicles/{vehicle_id}/odometer", status_code=201)
async def log_vehicle_odometer(vehicle_id: str, payload: OdometerInput, user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Fleet Manager", "Administrator")
    vehicle = await locked_record(session, Vehicle, vehicle_id)
    log = await add_odometer_log(session, vehicle, payload.value_km, "manual entry", logged_at=payload.logged_at)
    await audit(session, user, "vehicle.odometer_logged", "vehicle", vehicle.id, None, {"value_km": log.value_km, "source": log.source})
    return {"id": log.id, "date": log.logged_at.isoformat(), "value_km": log.value_km, "source": log.source}


@app.post("/api/vehicles/{vehicle_id}/documents", status_code=201)
async def create_vehicle_document(vehicle_id: str, payload: VehicleDocumentInput, user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Fleet Manager", "Administrator")
    await require_record(session, Vehicle, vehicle_id)
    if payload.expiry_date < payload.start_date:
        raise HTTPException(status_code=422, detail="The document expiry date cannot be before its start date.")
    document = VehicleDocument(id=f"doc-{uuid4().hex[:10]}", vehicle_id=vehicle_id, **payload.model_dump(), status="Active")
    session.add(document)
    await audit(session, user, "vehicle.document_added", "vehicle_document", document.id, None, document_value(document))
    return document_value(document)


@app.post("/api/vehicle-documents/{document_id}/renew", status_code=201)
async def renew_vehicle_document(document_id: str, payload: VehicleDocumentRenewInput, user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Fleet Manager", "Administrator")
    previous = await locked_record(session, VehicleDocument, document_id)
    if previous.status == "Renewed":
        raise HTTPException(status_code=409, detail="This document has already been renewed.")
    if payload.expiry_date < payload.start_date:
        raise HTTPException(status_code=422, detail="The document expiry date cannot be before its start date.")
    before = document_value(previous)
    previous.status = "Renewed"
    values = payload.model_dump()
    values["document_type"] = values["document_type"] or previous.document_type
    renewed = VehicleDocument(id=f"doc-{uuid4().hex[:10]}", vehicle_id=previous.vehicle_id, **values, status="Active")
    session.add(renewed)
    await audit(session, user, "vehicle.document_renewed", "vehicle_document", previous.id, before, {"previous": document_value(previous), "renewed": document_value(renewed)})
    return {"previous": document_value(previous), "renewed": document_value(renewed)}


@app.post("/api/vehicles/{vehicle_id}/retire")
async def retire_vehicle(vehicle_id: str, user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Fleet Manager", "Administrator")
    vehicle = await locked_record(session, Vehicle, vehicle_id)
    if vehicle.status == "On Trip":
        raise HTTPException(status_code=409, detail="Complete or cancel the active trip before retiring this vehicle.")
    active = await session.scalar(select(Maintenance.id).where(Maintenance.vehicle_id == vehicle_id, Maintenance.status.in_(["Scheduled", "In Progress"])).limit(1))
    if active:
        raise HTTPException(status_code=409, detail="Close active maintenance before retiring this vehicle.")
    before = vehicle_value(vehicle)
    vehicle.status = "Retired"
    await audit(session, user, "vehicle.retired", "vehicle", vehicle.id, before, vehicle_value(vehicle))
    return vehicle_value(vehicle)


@app.get("/api/drivers")
async def list_drivers(user: CurrentUser, session: Session) -> list[dict[str, Any]]:
    require_permission(user, "drivers")
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
async def list_trips(user: CurrentUser, session: Session) -> list[dict[str, Any]]:
    require_permission(user, "trips")
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
async def complete(trip_id: str, user: CurrentUser, session: Session, payload: TripCompletionInput | None = None) -> dict[str, Any]:
    trip = await locked_record(session, Trip, trip_id)
    if user.role.name == "Driver":
        if not user.driver_id or user.driver_id != trip.driver_id:
            raise HTTPException(status_code=403, detail="A driver can only complete their own assigned trip.")
    else:
        require(user, "Dispatcher", "Fleet Manager", "Administrator")
    if trip.status not in ("Dispatched", "In Progress"):
        raise HTTPException(status_code=409, detail="Only dispatched or in-progress trips can be completed.")
    before = trip_value(trip)
    trip.status, trip.completed_at = "Completed", datetime.now(UTC).replace(tzinfo=None)
    if payload and payload.actual_distance_km is not None:
        trip.actual_distance_km = payload.actual_distance_km
    if payload and payload.odometer_km is not None:
        vehicle = await locked_record(session, Vehicle, trip.vehicle_id)
        await add_odometer_log(session, vehicle, payload.odometer_km, "trip completion", trip.driver_id)
    await release_trip_resources(session, trip)
    await end_tracking_for_trip(session, trip.id, "TRIP_COMPLETED", user.id)
    await audit(session, user, "trip.completed", "trip", trip.id, before, trip_value(trip))
    return await decorated_trip(session, trip)


@app.post("/api/trips/{trip_id}/cancel")
async def cancel(trip_id: str, user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Dispatcher", "Fleet Manager", "Administrator")
    trip = await locked_record(session, Trip, trip_id)
    if trip.status not in ("Draft", "Dispatched", "In Progress"):
        raise HTTPException(status_code=409, detail="Only draft, dispatched, or in-progress trips can be cancelled.")
    before = trip_value(trip)
    if trip.status in ("Dispatched", "In Progress"):
        await release_trip_resources(session, trip)
        await end_tracking_for_trip(session, trip.id, "TRIP_CANCELLED", user.id)
    trip.status, trip.cancellation_reason = "Cancelled", "Cancelled by dispatcher"
    await audit(session, user, "trip.cancelled", "trip", trip.id, before, trip_value(trip))
    return await decorated_trip(session, trip)


@app.get("/api/maintenance")
async def list_maintenance(user: CurrentUser, session: Session) -> list[dict[str, Any]]:
    require_permission(user, "maintenance")
    records = (await session.scalars(select(Maintenance).order_by(Maintenance.opened_at.desc()))).all()
    return [await decorated_maintenance(session, record) for record in records]


@app.post("/api/maintenance", status_code=201)
async def create_maintenance(payload: MaintenanceInput, user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Fleet Manager", "Administrator")
    vehicle = await locked_record(session, Vehicle, payload.vehicle_id)
    if vehicle.status == "On Trip": raise HTTPException(status_code=409, detail="A vehicle on an active trip cannot enter maintenance.")
    if vehicle.status == "Retired": raise HTTPException(status_code=409, detail="A retired vehicle cannot enter maintenance.")
    active = await session.scalar(select(Maintenance.id).where(Maintenance.vehicle_id == vehicle.id, Maintenance.status.in_(["Scheduled", "In Progress"])).limit(1))
    if active: raise HTTPException(status_code=409, detail="This vehicle already has active maintenance.")
    record = Maintenance(id=f"m-{uuid4().hex[:8]}", **payload.model_dump(), opened_at=date.today())
    session.add(record)
    if payload.status == "In Progress":
        vehicle.status = "In Shop"
    if payload.odometer_km is not None:
        await add_odometer_log(session, vehicle, payload.odometer_km, "maintenance")
    await audit(session, user, "maintenance.scheduled", "maintenance", record.id, None, maintenance_value(record))
    return await decorated_maintenance(session, record)


@app.post("/api/maintenance/{maintenance_id}/start")
async def start_maintenance(maintenance_id: str, user: CurrentUser, session: Session, payload: OdometerInput | None = None) -> dict[str, Any]:
    require(user, "Fleet Manager", "Administrator")
    record = await locked_record(session, Maintenance, maintenance_id)
    if record.status != "Scheduled":
        raise HTTPException(status_code=409, detail="Only scheduled maintenance can be started.")
    vehicle = await locked_record(session, Vehicle, record.vehicle_id)
    if vehicle.status in ("On Trip", "Retired"):
        raise HTTPException(status_code=409, detail=f"A {vehicle.status} vehicle cannot enter maintenance.")
    before = maintenance_value(record)
    record.status = "In Progress"
    vehicle.status = "In Shop"
    if payload and payload.value_km is not None:
        record.odometer_km = payload.value_km
        await add_odometer_log(session, vehicle, payload.value_km, "maintenance", logged_at=payload.logged_at)
    await audit(session, user, "maintenance.started", "maintenance", record.id, before, maintenance_value(record))
    return await decorated_maintenance(session, record)


@app.post("/api/maintenance/{maintenance_id}/close")
async def close_maintenance(maintenance_id: str, user: CurrentUser, session: Session, payload: OdometerInput | None = None) -> dict[str, Any]:
    require(user, "Fleet Manager", "Administrator")
    record = await locked_record(session, Maintenance, maintenance_id)
    if record.status != "In Progress": raise HTTPException(status_code=409, detail="Only in-progress maintenance can be completed.")
    before = maintenance_value(record)
    record.status, record.closed_at = "Completed", date.today()
    vehicle = await locked_record(session, Vehicle, record.vehicle_id)
    if payload and payload.value_km is not None:
        record.odometer_km = payload.value_km
        await add_odometer_log(session, vehicle, payload.value_km, "maintenance", logged_at=payload.logged_at)
    active = await session.scalar(select(Maintenance.id).where(Maintenance.vehicle_id == vehicle.id, Maintenance.status == "In Progress", Maintenance.id != record.id).limit(1))
    if not active and vehicle.status != "Retired": vehicle.status = "Available"
    await audit(session, user, "maintenance.closed", "maintenance", record.id, before, maintenance_value(record))
    return await decorated_maintenance(session, record)


@app.post("/api/maintenance/{maintenance_id}/cancel")
async def cancel_maintenance(maintenance_id: str, user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Fleet Manager", "Administrator")
    record = await locked_record(session, Maintenance, maintenance_id)
    if record.status not in ("Scheduled", "In Progress"):
        raise HTTPException(status_code=409, detail="Only scheduled or in-progress maintenance can be cancelled.")
    before = maintenance_value(record)
    record.status, record.closed_at = "Cancelled", date.today()
    vehicle = await locked_record(session, Vehicle, record.vehicle_id)
    active = await session.scalar(select(Maintenance.id).where(Maintenance.vehicle_id == vehicle.id, Maintenance.status == "In Progress", Maintenance.id != record.id).limit(1))
    if not active and vehicle.status == "In Shop":
        vehicle.status = "Available"
    await audit(session, user, "maintenance.cancelled", "maintenance", record.id, before, maintenance_value(record))
    return await decorated_maintenance(session, record)


@app.get("/api/finance")
async def finance(user: CurrentUser, session: Session) -> dict[str, Any]:
    require_permission(user, "finance")
    fuel_logs = (await session.scalars(select(FuelLog).order_by(FuelLog.logged_at.desc()))).all()
    expenses = (await session.scalars(select(Expense).order_by(Expense.logged_at.desc()))).all()
    maintenance = (await session.scalars(select(Maintenance))).all()
    vehicle_names = {vehicle.id: vehicle.name for vehicle in (await session.scalars(select(Vehicle))).all()}
    fuel_cost = sum(log.cost for log in fuel_logs)
    maintenance_cost = sum(record.cost for record in maintenance)
    operational_cost = fuel_cost + maintenance_cost + sum(item.amount for item in expenses)
    return {"fuelLogs": [{"id": log.id, "vehicle_id": log.vehicle_id, "vehicle": vehicle_names[log.vehicle_id], "trip_id": log.trip_id, "date": log.logged_at.isoformat(), "liters": log.liters, "cost": log.cost, "odometer_km": log.odometer_km, "vendor": log.vendor} for log in fuel_logs], "expenses": [{"id": item.id, "category": item.category, "amount": item.amount, "vehicle_id": item.vehicle_id, "vehicle": vehicle_names.get(item.vehicle_id, "-"), "trip_id": item.trip_id, "date": item.logged_at.isoformat(), "notes": item.notes} for item in expenses], "operationalCost": operational_cost, "expandedCost": operational_cost, "costDefinition": "Fuel + maintenance + tolls + miscellaneous expenses"}


@app.post("/api/finance/fuel", status_code=201)
async def add_fuel(payload: FuelInput, user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Financial Analyst", "Fleet Manager", "Administrator")
    vehicle = await locked_record(session, Vehicle, payload.vehicle_id)
    trip = await require_record(session, Trip, payload.trip_id) if payload.trip_id else None
    record = FuelLog(id=f"f-{uuid4().hex[:8]}", **payload.model_dump(), logged_at=date.today())
    session.add(record)
    await add_odometer_log(session, vehicle, payload.odometer_km, "fuel log", trip.driver_id if trip else None)
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
async def analytics(user: CurrentUser, session: Session, date_from: date | None = None, date_to: date | None = None, vehicle_id: str | None = None) -> dict[str, Any]:
    require_permission(user, "analytics")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must be on or before date_to.")
    fuel_logs = (await session.scalars(select(FuelLog))).all()
    maintenance = (await session.scalars(select(Maintenance))).all()
    trips = (await session.scalars(select(Trip))).all()
    all_vehicles = (await session.scalars(select(Vehicle))).all()
    if vehicle_id and vehicle_id not in {vehicle.id for vehicle in all_vehicles}:
        raise HTTPException(status_code=404, detail="Vehicle not found.")
    vehicles = [vehicle for vehicle in all_vehicles if not vehicle_id or vehicle.id == vehicle_id]
    fuel_logs = [item for item in fuel_logs if (not vehicle_id or item.vehicle_id == vehicle_id) and (not date_from or item.logged_at >= date_from) and (not date_to or item.logged_at <= date_to)]
    maintenance = [item for item in maintenance if (not vehicle_id or item.vehicle_id == vehicle_id) and (not date_from or item.opened_at >= date_from) and (not date_to or item.opened_at <= date_to)]
    trips = [item for item in trips if (not vehicle_id or item.vehicle_id == vehicle_id) and (not date_from or item.created_at.date() >= date_from) and (not date_to or item.created_at.date() <= date_to)]
    expenses = (await session.scalars(select(Expense))).all()
    expenses = [item for item in expenses if (not vehicle_id or item.vehicle_id == vehicle_id) and (not date_from or item.logged_at >= date_from) and (not date_to or item.logged_at <= date_to)]
    fuel_cost, maintenance_cost = sum(item.cost for item in fuel_logs), sum(item.cost for item in maintenance)
    total_litres = sum(item.liters for item in fuel_logs)
    completed_distance = sum((trip.actual_distance_km or trip.planned_distance_km) for trip in trips if trip.status == "Completed")
    active_vehicles = [vehicle for vehicle in vehicles if vehicle.status != "Retired"]
    revenue = sum(trip.revenue for trip in trips if trip.status == "Completed")
    acquisition_cost = sum(vehicle.acquisition_cost for vehicle in active_vehicles)
    costs = [{"vehicle": vehicle.name, "cost": sum(item.cost for item in fuel_logs if item.vehicle_id == vehicle.id) + sum(item.cost for item in maintenance if item.vehicle_id == vehicle.id) + sum(item.amount for item in expenses if item.vehicle_id == vehicle.id)} for vehicle in vehicles]
    expense_cost = sum(item.amount for item in expenses)
    operational_cost = fuel_cost + maintenance_cost + expense_cost
    monthly: dict[str, float] = {}
    for trip in trips:
        if trip.status == "Completed":
            key = trip.completed_at.strftime("%Y-%m") if trip.completed_at else trip.created_at.strftime("%Y-%m")
            monthly[key] = monthly.get(key, 0) + trip.revenue
    return {"generated_at": datetime.now(UTC).isoformat(), "scope": {"date_from": date_from.isoformat() if date_from else None, "date_to": date_to.isoformat() if date_to else None, "vehicle_id": vehicle_id}, "metrics": {"fuelEfficiency": round(completed_distance / total_litres, 1) if total_litres else None, "utilization": round(sum(vehicle.status == "On Trip" for vehicle in active_vehicles) / len(active_vehicles) * 100) if active_vehicles else 0, "operationalCost": operational_cost, "roi": round((revenue - operational_cost) / acquisition_cost * 100, 1) if acquisition_cost else None}, "revenue": [{"month": key, "amount": amount} for key, amount in sorted(monthly.items())], "costliestVehicles": sorted(costs, key=lambda item: item["cost"], reverse=True), "filterOptions": {"vehicles": [{"id": vehicle.id, "name": vehicle.name} for vehicle in all_vehicles]}}


@app.get("/api/analytics/export")
async def export_analytics(user: CurrentUser, session: Session, date_from: date | None = None, date_to: date | None = None, vehicle_id: str | None = None) -> Response:
    require_permission(user, "analytics")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must be on or before date_to.")
    fuel_logs = (await session.scalars(select(FuelLog))).all()
    maintenance = (await session.scalars(select(Maintenance))).all()
    expenses = (await session.scalars(select(Expense))).all()
    vehicles = (await session.scalars(select(Vehicle))).all()
    if vehicle_id and vehicle_id not in {vehicle.id for vehicle in vehicles}:
        raise HTTPException(status_code=404, detail="Vehicle not found.")
    fuel_logs = [item for item in fuel_logs if (not vehicle_id or item.vehicle_id == vehicle_id) and (not date_from or item.logged_at >= date_from) and (not date_to or item.logged_at <= date_to)]
    maintenance = [item for item in maintenance if (not vehicle_id or item.vehicle_id == vehicle_id) and (not date_from or item.opened_at >= date_from) and (not date_to or item.opened_at <= date_to)]
    expenses = [item for item in expenses if (not vehicle_id or item.vehicle_id == vehicle_id) and (not date_from or item.logged_at >= date_from) and (not date_to or item.logged_at <= date_to)]
    vehicles = [vehicle for vehicle in vehicles if not vehicle_id or vehicle.id == vehicle_id]
    rows = ["vehicle,operational_cost", *[f'"{vehicle.name}",{sum(item.cost for item in fuel_logs if item.vehicle_id == vehicle.id) + sum(item.cost for item in maintenance if item.vehicle_id == vehicle.id) + sum(item.amount for item in expenses if item.vehicle_id == vehicle.id):.2f}' for vehicle in vehicles]]
    return Response("\n".join(rows) + "\n", media_type="text/csv", headers={"Content-Disposition": "attachment; filename=transitops-analytics.csv"})


@app.get("/api/settings")
async def get_settings(user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Fleet Manager", "Administrator")
    preferences = await require_record(session, Preference, 1)
    return {field: getattr(preferences, field) for field in PreferencesInput.model_fields}


@app.put("/api/settings")
async def update_settings(payload: PreferencesInput, user: CurrentUser, session: Session) -> dict[str, Any]:
    require(user, "Fleet Manager", "Administrator")
    preferences = await require_record(session, Preference, 1)
    before = {field: getattr(preferences, field) for field in PreferencesInput.model_fields}
    for field, value in payload.model_dump().items(): setattr(preferences, field, value)
    after = {field: getattr(preferences, field) for field in PreferencesInput.model_fields}
    await audit(session, user, "preferences.updated", "preferences", "1", before, after)
    return after
