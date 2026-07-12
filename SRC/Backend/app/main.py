from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from threading import RLock
from typing import Any, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from jose import JWTError, jwt
from passlib.context import CryptContext


VehicleStatus = Literal["Available", "On Trip", "In Shop", "Retired"]
DriverStatus = Literal["Available", "On Trip", "Off Duty", "Suspended"]
TripStatus = Literal["Draft", "Dispatched", "Completed", "Cancelled"]
Role = Literal["Fleet Manager", "Dispatcher", "Safety Officer", "Financial Analyst", "Administrator"]
JWT_SECRET = os.getenv("TRANSITOPS_JWT_SECRET", "transitops-local-demo-secret-change-in-production")
JWT_ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
    image_position: int = Field(default=0, ge=0, le=3)


class DriverInput(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    license_number: str = Field(min_length=3, max_length=32)
    license_category: str = "LMV"
    license_expiry: date
    contact: str = Field(min_length=5, max_length=30)
    safety_score: float = Field(ge=0, le=100)
    status: DriverStatus = "Available"
    region: str = "Ahmedabad"
    photo_position: int = Field(default=0, ge=0, le=3)


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


def normalise(value: str) -> str:
    return "".join(value.upper().split())


class DemoStore:
    """A deliberately small repository for the demo slice; services still own the rules."""

    def __init__(self) -> None:
        self.lock = RLock()
        demo_password = pwd_context.hash("demo")
        self.users = [
            {"id": "u-fleet", "name": "Raven Kapoor", "email": "fleet@transitops.demo", "role": "Fleet Manager", "password_hash": demo_password},
            {"id": "u-dispatch", "name": "Aarav Shah", "email": "dispatcher@transitops.demo", "role": "Dispatcher", "password_hash": demo_password},
            {"id": "u-safety", "name": "Priya Iyer", "email": "safety@transitops.demo", "role": "Safety Officer", "password_hash": demo_password},
            {"id": "u-finance", "name": "Ishaan Mehta", "email": "finance@transitops.demo", "role": "Financial Analyst", "password_hash": demo_password},
        ]
        self.vehicles = [
            {"id": "v-van05", "registration": "GJ 01 AB 1234", "name": "Van-05", "vehicle_type": "Van", "capacity_kg": 500, "odometer_km": 42850, "acquisition_cost": 850000, "region": "Ahmedabad", "status": "Available", "image_position": 0},
            {"id": "v-truck11", "registration": "GJ 01 CD 8871", "name": "Truck-11", "vehicle_type": "Truck", "capacity_kg": 5000, "odometer_km": 119340, "acquisition_cost": 2250000, "region": "Ahmedabad", "status": "On Trip", "image_position": 1},
            {"id": "v-mini03", "registration": "GJ 27 MN 2203", "name": "Mini-03", "vehicle_type": "Mini Truck", "capacity_kg": 1200, "odometer_km": 67830, "acquisition_cost": 1180000, "region": "Surat", "status": "In Shop", "image_position": 2},
            {"id": "v-car02", "registration": "GJ 01 EF 4132", "name": "Car-02", "vehicle_type": "Car", "capacity_kg": 300, "odometer_km": 91500, "acquisition_cost": 620000, "region": "Ahmedabad", "status": "Retired", "image_position": 3},
        ]
        self.drivers = [
            {"id": "d-alex", "name": "Alex Thomas", "license_number": "GJ-DRV-1088", "license_category": "LMV", "license_expiry": "2027-10-14", "contact": "+91 98765 32010", "safety_score": 94, "status": "Available", "region": "Ahmedabad", "photo_position": 0},
            {"id": "d-rahul", "name": "Rahul Patel", "license_number": "GJ-DRV-1205", "license_category": "HMV", "license_expiry": "2027-03-22", "contact": "+91 98765 10222", "safety_score": 88, "status": "On Trip", "region": "Ahmedabad", "photo_position": 1},
            {"id": "d-neha", "name": "Neha Desai", "license_number": "GJ-DRV-1779", "license_category": "LMV", "license_expiry": "2025-12-08", "contact": "+91 98765 76111", "safety_score": 91, "status": "Off Duty", "region": "Surat", "photo_position": 2},
            {"id": "d-samir", "name": "Samir Khan", "license_number": "GJ-DRV-1882", "license_category": "HMV", "license_expiry": "2027-06-01", "contact": "+91 98765 45789", "safety_score": 72, "status": "Suspended", "region": "Ahmedabad", "photo_position": 3},
        ]
        self.trips = [
            {"id": "TR-1042", "source": "Ahmedabad Depot", "destination": "Vadodara Hub", "vehicle_id": "v-truck11", "driver_id": "d-rahul", "cargo_kg": 3200, "planned_distance_km": 112, "actual_distance_km": None, "revenue": 18500, "notes": "Priority retail replenishment", "status": "Dispatched", "created_at": "2026-07-12T08:15:00", "completed_at": None, "cancellation_reason": None},
            {"id": "TR-1043", "source": "Ahmedabad Depot", "destination": "Gandhinagar", "vehicle_id": "v-van05", "driver_id": "d-alex", "cargo_kg": 420, "planned_distance_km": 38, "actual_distance_km": None, "revenue": 7200, "notes": "Draft delivery plan", "status": "Draft", "created_at": "2026-07-12T09:10:00", "completed_at": None, "cancellation_reason": None},
            {"id": "TR-1039", "source": "Surat", "destination": "Bharuch", "vehicle_id": "v-mini03", "driver_id": "d-neha", "cargo_kg": 700, "planned_distance_km": 78, "actual_distance_km": 81, "revenue": 12400, "notes": "Completed before workshop booking", "status": "Completed", "created_at": "2026-07-10T07:00:00", "completed_at": "2026-07-10T12:30:00", "cancellation_reason": None},
        ]
        self.maintenance = [
            {"id": "m-1", "vehicle_id": "v-mini03", "service_type": "Brake inspection", "cost": 18000, "status": "Active", "opened_at": "2026-07-11", "closed_at": None, "notes": "Workshop diagnosis in progress"},
            {"id": "m-2", "vehicle_id": "v-truck11", "service_type": "Oil change", "cost": 6400, "status": "Completed", "opened_at": "2026-06-20", "closed_at": "2026-06-21", "notes": "Scheduled service"},
        ]
        self.fuel_logs = [
            {"id": "f-1", "vehicle_id": "v-van05", "date": "2026-07-05", "liters": 42, "cost": 3150, "odometer_km": 42790, "vendor": "HP Fuel", "trip_id": None},
            {"id": "f-2", "vehicle_id": "v-truck11", "date": "2026-07-06", "liters": 110, "cost": 8400, "odometer_km": 118990, "vendor": "Indian Oil", "trip_id": "TR-1042"},
            {"id": "f-3", "vehicle_id": "v-mini03", "date": "2026-07-06", "liters": 28, "cost": 2050, "odometer_km": 67790, "vendor": "Shell", "trip_id": "TR-1039"},
        ]
        self.expenses = [
            {"id": "e-1", "category": "Toll", "amount": 340, "vehicle_id": "v-truck11", "trip_id": "TR-1042", "date": "2026-07-11", "notes": "Expressway"},
            {"id": "e-2", "category": "Miscellaneous", "amount": 150, "vehicle_id": "v-van05", "trip_id": "TR-1043", "date": "2026-07-10", "notes": "Loading supplies"},
        ]
        self.preferences = {"depot_name": "Gandhinagar Depot, Gujarat", "currency": "INR", "distance_unit": "Kilometres"}
        self.revoked_tokens: set[str] = set()
        self.login_attempts: dict[str, list[datetime]] = {}
        self.audit_events: list[dict[str, Any]] = []

    @staticmethod
    def by_id(items: list[dict[str, Any]], item_id: str) -> dict[str, Any]:
        item = next((item for item in items if item["id"] == item_id), None)
        if not item:
            raise HTTPException(status_code=404, detail="Record not found.")
        return item


store = DemoStore()
app = FastAPI(title="TransitOps API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {key: user[key] for key in ("id", "name", "email", "role")}


def audit(user: dict[str, Any], action: str, target: str) -> None:
    store.audit_events.append({"id": str(uuid4()), "actor_id": user["id"], "action": action, "target": target, "at": datetime.now(timezone.utc).isoformat()})


def current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in to continue.")
    token = authorization.removeprefix("Bearer ")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id, token_id = payload.get("sub"), payload.get("jti")
        if not user_id or not token_id or token_id in store.revoked_tokens:
            raise JWTError("Invalid session")
        user = dict(DemoStore.by_id(store.users, user_id))
        user["token_id"] = token_id
        return user
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your session is invalid or expired. Please sign in again.")


def require(user: dict[str, Any], *roles: Role) -> None:
    if user["role"] not in roles:
        raise HTTPException(status_code=403, detail="Your role does not have permission for this action.")


READ_ROLES: dict[str, tuple[Role, ...]] = {
    "vehicles": ("Fleet Manager", "Dispatcher", "Administrator"),
    "drivers": ("Fleet Manager", "Dispatcher", "Safety Officer", "Administrator"),
    "trips": ("Fleet Manager", "Dispatcher", "Safety Officer", "Administrator"),
    "maintenance": ("Fleet Manager", "Administrator"),
    "finance": ("Fleet Manager", "Financial Analyst", "Administrator"),
    "analytics": ("Fleet Manager", "Financial Analyst", "Administrator"),
}


def require_read(user: dict[str, Any], resource: str) -> None:
    require(user, *READ_ROLES[resource])


def decorated_trip(trip: dict[str, Any]) -> dict[str, Any]:
    value = dict(trip)
    value["vehicle"] = store.by_id(store.vehicles, trip["vehicle_id"])["name"]
    value["driver"] = store.by_id(store.drivers, trip["driver_id"])["name"]
    return value


def decorated_maintenance(record: dict[str, Any]) -> dict[str, Any]:
    value = dict(record)
    value["vehicle"] = store.by_id(store.vehicles, record["vehicle_id"])["name"]
    return value


def dispatch_trip(trip: dict[str, Any]) -> dict[str, Any]:
    if trip["status"] != "Draft":
        raise HTTPException(status_code=409, detail="Only draft trips can be dispatched.")
    vehicle = store.by_id(store.vehicles, trip["vehicle_id"])
    driver = store.by_id(store.drivers, trip["driver_id"])
    reasons: list[str] = []
    if vehicle["status"] != "Available":
        reasons.append(f"{vehicle['name']} is {vehicle['status']}.")
    if driver["status"] != "Available":
        reasons.append(f"{driver['name']} is {driver['status']}.")
    if date.fromisoformat(driver["license_expiry"]) < date.today():
        reasons.append(f"{driver['name']}'s licence is expired.")
    if trip["cargo_kg"] > vehicle["capacity_kg"]:
        reasons.append(f"Cargo exceeds capacity by {trip['cargo_kg'] - vehicle['capacity_kg']:.0f} kg.")
    if reasons:
        raise HTTPException(status_code=409, detail=" ".join(reasons))
    trip["status"] = "Dispatched"
    vehicle["status"] = "On Trip"
    driver["status"] = "On Trip"
    return decorated_trip(trip)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    attempts = [item for item in store.login_attempts.get(str(payload.email).lower(), []) if now - item < timedelta(minutes=15)]
    if len(attempts) >= 5:
        raise HTTPException(status_code=429, detail="Too many failed sign-in attempts. Try again in 15 minutes.")
    user = next((user for user in store.users if user["email"] == str(payload.email).lower()), None)
    if not user or not pwd_context.verify(payload.password, user["password_hash"]):
        store.login_attempts[str(payload.email).lower()] = attempts + [now]
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    store.login_attempts.pop(str(payload.email).lower(), None)
    token_id = str(uuid4())
    token = jwt.encode({"sub": user["id"], "jti": token_id, "exp": now + timedelta(hours=8)}, JWT_SECRET, algorithm=JWT_ALGORITHM)
    audit(user, "session.login", user["id"])
    return {"access_token": token, "user": public_user(user)}


@app.post("/api/auth/logout", status_code=204)
def logout(user: dict[str, Any] = Depends(current_user)) -> Response:
    store.revoked_tokens.add(user["token_id"])
    audit(user, "session.logout", user["id"])
    return Response(status_code=204)


@app.get("/api/dashboard")
def dashboard(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    active_vehicles = [vehicle for vehicle in store.vehicles if vehicle["status"] != "Retired"]
    status_counts = {key: sum(vehicle["status"] == key for vehicle in store.vehicles) for key in ["Available", "On Trip", "In Shop", "Retired"]}
    return {
        "kpis": {
            "activeVehicles": len(active_vehicles),
            "availableVehicles": status_counts["Available"],
            "inMaintenance": status_counts["In Shop"],
            "activeTrips": sum(trip["status"] == "Dispatched" for trip in store.trips),
            "pendingTrips": sum(trip["status"] == "Draft" for trip in store.trips),
            "driversOnDuty": sum(driver["status"] == "On Trip" for driver in store.drivers),
            "utilization": round((status_counts["On Trip"] / len(active_vehicles) * 100) if active_vehicles else 0),
        },
        "vehicleStatus": [{"name": key, "value": value} for key, value in status_counts.items()],
        "recentTrips": [decorated_trip(trip) for trip in sorted(store.trips, key=lambda trip: trip["created_at"], reverse=True)[:5]],
        "viewer": user,
    }


@app.get("/api/vehicles")
def list_vehicles(user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    require_read(user, "vehicles")
    return store.vehicles


@app.post("/api/vehicles", status_code=201)
def create_vehicle(payload: VehicleInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require(user, "Fleet Manager", "Administrator")
    with store.lock:
        if any(normalise(item["registration"]) == normalise(payload.registration) for item in store.vehicles):
            raise HTTPException(status_code=409, detail="A vehicle with this registration already exists.")
        vehicle = {"id": f"v-{uuid4().hex[:8]}", **payload.model_dump()}
        store.vehicles.append(vehicle)
        return vehicle


@app.patch("/api/vehicles/{vehicle_id}")
def update_vehicle(vehicle_id: str, payload: VehicleInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require(user, "Fleet Manager", "Administrator")
    with store.lock:
        vehicle = store.by_id(store.vehicles, vehicle_id)
        if vehicle["status"] == "On Trip" and payload.status != "On Trip":
            raise HTTPException(status_code=409, detail="Complete or cancel the active trip before changing vehicle state.")
        vehicle.update(payload.model_dump())
        return vehicle


@app.post("/api/vehicles/{vehicle_id}/retire")
def retire_vehicle(vehicle_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require(user, "Fleet Manager", "Administrator")
    with store.lock:
        vehicle = store.by_id(store.vehicles, vehicle_id)
        if vehicle["status"] == "On Trip":
            raise HTTPException(status_code=409, detail="Complete or cancel the active trip before retiring this vehicle.")
        if any(item["vehicle_id"] == vehicle_id and item["status"] == "Active" for item in store.maintenance):
            raise HTTPException(status_code=409, detail="Close active maintenance before retiring this vehicle.")
        vehicle["status"] = "Retired"
        return vehicle


@app.get("/api/drivers")
def list_drivers(user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    require_read(user, "drivers")
    return store.drivers


@app.post("/api/drivers", status_code=201)
def create_driver(payload: DriverInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require(user, "Fleet Manager", "Safety Officer", "Administrator")
    with store.lock:
        if any(normalise(item["license_number"]) == normalise(payload.license_number) for item in store.drivers):
            raise HTTPException(status_code=409, detail="A driver with this licence number already exists.")
        driver = {"id": f"d-{uuid4().hex[:8]}", **payload.model_dump(mode="json")}
        store.drivers.append(driver)
        return driver


@app.patch("/api/drivers/{driver_id}")
def update_driver(driver_id: str, payload: DriverInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require(user, "Fleet Manager", "Safety Officer", "Administrator")
    with store.lock:
        driver = store.by_id(store.drivers, driver_id)
        if driver["status"] == "On Trip" and payload.status != "On Trip":
            raise HTTPException(status_code=409, detail="Complete or cancel the active trip before changing driver state.")
        if any(normalise(item["license_number"]) == normalise(payload.license_number) and item["id"] != driver_id for item in store.drivers):
            raise HTTPException(status_code=409, detail="A driver with this licence number already exists.")
        driver.update(payload.model_dump(mode="json"))
        return driver


@app.get("/api/trips")
def list_trips(user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    require_read(user, "trips")
    return [decorated_trip(trip) for trip in sorted(store.trips, key=lambda trip: trip["created_at"], reverse=True)]


@app.post("/api/trips", status_code=201)
def create_trip(payload: TripInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require(user, "Dispatcher", "Fleet Manager", "Administrator")
    vehicle = store.by_id(store.vehicles, payload.vehicle_id)
    store.by_id(store.drivers, payload.driver_id)
    if payload.cargo_kg > vehicle["capacity_kg"]:
        raise HTTPException(status_code=422, detail=f"Cargo exceeds {vehicle['name']} capacity by {payload.cargo_kg - vehicle['capacity_kg']:.0f} kg.")
    trip = {"id": f"TR-{1000 + len(store.trips) + 1}", **payload.model_dump(), "actual_distance_km": None, "status": "Draft", "created_at": datetime.now().isoformat(timespec="seconds"), "completed_at": None, "cancellation_reason": None}
    with store.lock:
        store.trips.append(trip)
    return decorated_trip(trip)


@app.post("/api/trips/{trip_id}/dispatch")
def dispatch(trip_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require(user, "Dispatcher", "Fleet Manager", "Administrator")
    with store.lock:
        return dispatch_trip(store.by_id(store.trips, trip_id))


@app.post("/api/trips/{trip_id}/complete")
def complete(trip_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require(user, "Dispatcher", "Fleet Manager", "Administrator")
    with store.lock:
        trip = store.by_id(store.trips, trip_id)
        if trip["status"] != "Dispatched":
            raise HTTPException(status_code=409, detail="Only dispatched trips can be completed.")
        trip["status"] = "Completed"
        trip["completed_at"] = datetime.now().isoformat(timespec="seconds")
        vehicle = store.by_id(store.vehicles, trip["vehicle_id"])
        driver = store.by_id(store.drivers, trip["driver_id"])
        if vehicle["status"] == "On Trip":
            vehicle["status"] = "Available"
        if driver["status"] == "On Trip":
            driver["status"] = "Available"
        return decorated_trip(trip)


@app.post("/api/trips/{trip_id}/cancel")
def cancel(trip_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require(user, "Dispatcher", "Fleet Manager", "Administrator")
    with store.lock:
        trip = store.by_id(store.trips, trip_id)
        if trip["status"] not in ("Draft", "Dispatched"):
            raise HTTPException(status_code=409, detail="Only draft or dispatched trips can be cancelled.")
        if trip["status"] == "Dispatched":
            vehicle = store.by_id(store.vehicles, trip["vehicle_id"])
            driver = store.by_id(store.drivers, trip["driver_id"])
            if vehicle["status"] == "On Trip":
                vehicle["status"] = "Available"
            if driver["status"] == "On Trip":
                driver["status"] = "Available"
        trip["status"] = "Cancelled"
        trip["cancellation_reason"] = "Cancelled by dispatcher"
        return decorated_trip(trip)


@app.get("/api/maintenance")
def list_maintenance(user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    require_read(user, "maintenance")
    return [decorated_maintenance(record) for record in store.maintenance]


@app.post("/api/maintenance", status_code=201)
def create_maintenance(payload: MaintenanceInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require(user, "Fleet Manager", "Administrator")
    with store.lock:
        vehicle = store.by_id(store.vehicles, payload.vehicle_id)
        if vehicle["status"] == "On Trip":
            raise HTTPException(status_code=409, detail="A vehicle on an active trip cannot enter maintenance.")
        if vehicle["status"] == "Retired":
            raise HTTPException(status_code=409, detail="A retired vehicle cannot enter maintenance.")
        if any(item["vehicle_id"] == vehicle["id"] and item["status"] == "Active" for item in store.maintenance):
            raise HTTPException(status_code=409, detail="This vehicle already has active maintenance.")
        record = {"id": f"m-{uuid4().hex[:8]}", **payload.model_dump(), "status": "Active", "opened_at": date.today().isoformat(), "closed_at": None}
        store.maintenance.append(record)
        vehicle["status"] = "In Shop"
        return decorated_maintenance(record)


@app.post("/api/maintenance/{maintenance_id}/close")
def close_maintenance(maintenance_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require(user, "Fleet Manager", "Administrator")
    with store.lock:
        record = store.by_id(store.maintenance, maintenance_id)
        if record["status"] != "Active":
            raise HTTPException(status_code=409, detail="This maintenance record is already closed.")
        record["status"] = "Completed"
        record["closed_at"] = date.today().isoformat()
        vehicle = store.by_id(store.vehicles, record["vehicle_id"])
        has_active = any(item["vehicle_id"] == vehicle["id"] and item["status"] == "Active" for item in store.maintenance)
        if not has_active and vehicle["status"] != "Retired":
            vehicle["status"] = "Available"
        return decorated_maintenance(record)


@app.get("/api/finance")
def finance(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_read(user, "finance")
    def fuel(log: dict[str, Any]) -> dict[str, Any]:
        return {**log, "vehicle": store.by_id(store.vehicles, log["vehicle_id"])["name"]}
    def expense(item: dict[str, Any]) -> dict[str, Any]:
        return {**item, "vehicle": store.by_id(store.vehicles, item["vehicle_id"])["name"] if item["vehicle_id"] else "-"}
    maintenance_cost = sum(item["cost"] for item in store.maintenance)
    fuel_cost = sum(item["cost"] for item in store.fuel_logs)
    return {"fuelLogs": [fuel(log) for log in store.fuel_logs], "expenses": [expense(item) for item in store.expenses], "operationalCost": fuel_cost + maintenance_cost, "expandedCost": fuel_cost + maintenance_cost + sum(item["amount"] for item in store.expenses)}


@app.post("/api/finance/fuel", status_code=201)
def add_fuel(payload: FuelInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require(user, "Financial Analyst", "Fleet Manager", "Administrator")
    store.by_id(store.vehicles, payload.vehicle_id)
    record = {"id": f"f-{uuid4().hex[:8]}", **payload.model_dump(), "date": date.today().isoformat()}
    store.fuel_logs.append(record)
    return record


@app.post("/api/finance/expenses", status_code=201)
def add_expense(payload: ExpenseInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require(user, "Financial Analyst", "Fleet Manager", "Administrator")
    record = {"id": f"e-{uuid4().hex[:8]}", **payload.model_dump(), "date": date.today().isoformat()}
    store.expenses.append(record)
    return record


@app.get("/api/analytics")
def analytics(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_read(user, "analytics")
    fuel_cost = sum(item["cost"] for item in store.fuel_logs)
    maintenance_cost = sum(item["cost"] for item in store.maintenance)
    total_litres = sum(item["liters"] for item in store.fuel_logs)
    completed_distance = sum((trip["actual_distance_km"] or trip["planned_distance_km"]) for trip in store.trips if trip["status"] == "Completed")
    active_vehicles = [vehicle for vehicle in store.vehicles if vehicle["status"] != "Retired"]
    revenue = sum(trip["revenue"] for trip in store.trips if trip["status"] in ("Completed", "Dispatched"))
    acquisition_cost = sum(vehicle["acquisition_cost"] for vehicle in active_vehicles)
    cost_by_vehicle = []
    for vehicle in store.vehicles:
        cost = sum(item["cost"] for item in store.fuel_logs if item["vehicle_id"] == vehicle["id"]) + sum(item["cost"] for item in store.maintenance if item["vehicle_id"] == vehicle["id"])
        cost_by_vehicle.append({"vehicle": vehicle["name"], "cost": cost})
    return {
        "metrics": {"fuelEfficiency": round(completed_distance / total_litres, 1) if total_litres else None, "utilization": round(sum(vehicle["status"] == "On Trip" for vehicle in active_vehicles) / len(active_vehicles) * 100) if active_vehicles else 0, "operationalCost": fuel_cost + maintenance_cost, "roi": round((revenue - fuel_cost - maintenance_cost) / acquisition_cost * 100, 1) if acquisition_cost else None},
        "revenue": [{"month": "Apr", "amount": 16200}, {"month": "May", "amount": 22400}, {"month": "Jun", "amount": 19500}, {"month": "Jul", "amount": revenue}],
        "costliestVehicles": sorted(cost_by_vehicle, key=lambda item: item["cost"], reverse=True),
    }


@app.get("/api/analytics/export")
def export_analytics(user: dict[str, Any] = Depends(current_user)) -> Response:
    require_read(user, "analytics")
    rows = ["vehicle,operational_cost"]
    for vehicle in store.vehicles:
        cost = sum(item["cost"] for item in store.fuel_logs if item["vehicle_id"] == vehicle["id"]) + sum(item["cost"] for item in store.maintenance if item["vehicle_id"] == vehicle["id"])
        rows.append(f'"{vehicle["name"]}",{cost:.2f}')
    return Response("\n".join(rows) + "\n", media_type="text/csv", headers={"Content-Disposition": "attachment; filename=transitops-analytics.csv"})


@app.get("/api/settings")
def get_settings(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require(user, "Fleet Manager", "Administrator")
    return store.preferences


@app.put("/api/settings")
def update_settings(payload: PreferencesInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require(user, "Fleet Manager", "Administrator")
    with store.lock:
        store.preferences = payload.model_dump()
        return store.preferences
