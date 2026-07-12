from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from math import atan2, cos, radians, sin, sqrt
import json
import os
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_session
from .models import (
    AuditEvent,
    Driver,
    DriverTrackingSession,
    Geofence,
    GeofenceEvent,
    LatestVehicleLocation,
    Preference,
    TrackingAlert,
    Trip,
    User,
    Vehicle,
    VehicleLocationPoint,
    utc_now,
)
from .routing import RouteResult, StraightLineDirectionsProvider, directions_provider


router = APIRouter(prefix="/api", tags=["fleet-tracking"])
Session = Annotated[AsyncSession, Depends(get_session)]
TRACKING_RATE_LIMIT_PER_MINUTE = int(os.getenv("TRACKING_RATE_LIMIT_PER_MINUTE", "120"))
TRACKING_MAX_BATCH_SIZE = int(os.getenv("TRACKING_MAX_BATCH_SIZE", "100"))
CONSENT_VERSION = "2026-07"
ACTIVE_TRIP_STATUSES = ("Dispatched", "In Progress")
TRACKING_VIEW_ROLES = ("Fleet Manager", "Dispatcher", "Safety Officer", "Administrator")
TRACKING_MANAGE_ROLES = ("Fleet Manager", "Administrator")
ROLE_TRACKING_PERMISSIONS = {
    "Fleet Manager": {"tracking.view_all", "tracking.view_depot", "tracking.history.view", "tracking.settings.manage", "geofences.view", "geofences.manage"},
    "Dispatcher": {"tracking.view_depot", "tracking.history.view", "geofences.view"},
    "Safety Officer": {"tracking.view_depot", "tracking.history.view", "geofences.view"},
    "Financial Analyst": set(),
    "Administrator": {"tracking.view_all", "tracking.view_depot", "tracking.history.view", "tracking.settings.manage", "geofences.view", "geofences.manage"},
    "Driver": {"tracking.view_own", "tracking.session.start", "tracking.session.end"},
}


class StartTrackingInput(BaseModel):
    consent: bool
    consent_version: str = CONSENT_VERSION


class LocationInput(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=100)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_meters: float = Field(ge=0, le=10000)
    altitude: float | None = None
    altitude_accuracy: float | None = Field(default=None, ge=0)
    heading_degrees: float | None = Field(default=None, ge=0, le=360)
    speed_mps: float | None = Field(default=None, ge=0, le=150)
    captured_at: datetime
    battery_percentage: float | None = Field(default=None, ge=0, le=100)
    network_state: str | None = Field(default=None, max_length=30)
    is_mock_location: bool | None = None
    metadata: dict[str, Any] | None = None
    # These are deliberately ignored for association and exist only so tests and
    # older clients can prove that server-side derivation wins.
    driver_id: str | None = None
    vehicle_id: str | None = None
    trip_id: str | None = None

    @field_validator("captured_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value


class LocationBatchInput(BaseModel):
    points: list[LocationInput] = Field(min_length=1)

    @field_validator("points")
    @classmethod
    def bound_batch(cls, points: list[LocationInput]) -> list[LocationInput]:
        if len(points) > TRACKING_MAX_BATCH_SIZE:
            raise ValueError(f"A batch can contain at most {TRACKING_MAX_BATCH_SIZE} points.")
        return points


class GeofenceInput(BaseModel):
    depot_id: str = Field(min_length=2, max_length=100)
    name: str = Field(min_length=2, max_length=100)
    type: Literal["DEPOT", "CUSTOMER", "WAREHOUSE", "RESTRICTED", "CUSTOM"]
    center_latitude: float = Field(ge=-90, le=90)
    center_longitude: float = Field(ge=-180, le=180)
    radius_meters: float = Field(gt=0, le=100000)
    polygon_geojson: dict[str, Any] | None = None
    is_active: bool = True


class TrackingIssueInput(BaseModel):
    issue_type: Literal["DRIVER_EMERGENCY", "GPS_FAILURE", "VEHICLE_ISSUE", "ROUTE_BLOCKED"]
    message: str = Field(min_length=5, max_length=300)


class TrackingEventBroker:
    def __init__(self) -> None:
        self.queues: set[asyncio.Queue[dict[str, Any]]] = set()

    async def publish(self, event: dict[str, Any]) -> None:
        for queue in list(self.queues):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def subscribe(self) -> AsyncIterator[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        self.queues.add(queue)
        try:
            while True:
                try:
                    yield await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield {"type": "heartbeat", "sent_at": utc_now().isoformat()}
        finally:
            self.queues.discard(queue)


broker = TrackingEventBroker()
request_times: dict[str, deque[datetime]] = defaultdict(deque)
route_cache: dict[str, RouteResult] = {}


async def current_tracking_user(session: Session, authorization: str | None = Header(default=None)) -> User:
    if not authorization or not authorization.startswith("Bearer demo-"):
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    user = await session.get(User, authorization.removeprefix("Bearer demo-"))
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    return user


CurrentTrackingUser = Annotated[User, Depends(current_tracking_user)]


def role_name(user: User) -> str:
    return user.role.name


def require_roles(user: User, *roles: str) -> None:
    if role_name(user) not in roles:
        raise HTTPException(status_code=403, detail="Your role does not have permission for live location data.")


def require_permission(user: User, permission: str) -> None:
    if permission not in ROLE_TRACKING_PERMISSIONS.get(role_name(user), set()):
        raise HTTPException(status_code=403, detail=f"Missing required permission: {permission}.")


async def audit(session: AsyncSession, user: User, event_type: str, target_type: str, target_id: str, before: dict[str, Any] | None = None, after: dict[str, Any] | None = None) -> None:
    session.add(AuditEvent(id=f"audit-{uuid4().hex[:12]}", actor_id=user.id, event_type=event_type, target_type=target_type, target_id=target_id, before_state=before, after_state=after))


async def preferences(session: AsyncSession) -> Preference:
    value = await session.get(Preference, 1)
    if not value:
        raise HTTPException(status_code=503, detail="Tracking settings are not configured.")
    return value


def ensure_rate_limit(user_id: str, amount: int = 1) -> None:
    now = utc_now()
    cutoff = now - timedelta(minutes=1)
    bucket = request_times[user_id]
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    if len(bucket) + amount > TRACKING_RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Location update rate limit exceeded. Retry shortly.")
    bucket.extend(now for _ in range(amount))


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius = 6_371_000
    lat1_r, lat2_r = radians(lat1), radians(lat2)
    d_lat, d_lon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(lat1_r) * cos(lat2_r) * sin(d_lon / 2) ** 2
    return earth_radius * 2 * atan2(sqrt(a), sqrt(1 - a))


def tracking_state(location: LatestVehicleLocation | None, settings: Preference) -> tuple[str, str]:
    if not location:
        return "OFFLINE", "GPS_UNAVAILABLE"
    age = max(0, (utc_now() - location.received_at).total_seconds())
    if age > settings.tracking_offline_seconds:
        return "OFFLINE", "STOPPED"
    if age > settings.tracking_stale_seconds:
        return "STALE", "STOPPED"
    return "ONLINE", "MOVING" if (location.speed_mps or 0) >= 1.4 else "STOPPED"


def session_value(value: DriverTrackingSession) -> dict[str, Any]:
    return {"id": value.id, "driver_id": value.driver_id, "vehicle_id": value.vehicle_id, "trip_id": value.trip_id, "status": value.status, "started_at": value.started_at.isoformat(), "ended_at": value.ended_at.isoformat() if value.ended_at else None, "last_location_at": value.last_location_at.isoformat() if value.last_location_at else None, "consent_version": value.consent_version}


async def active_trip_for_driver(session: AsyncSession, driver_id: str) -> Trip | None:
    return await session.scalar(select(Trip).where(Trip.driver_id == driver_id, Trip.status.in_(ACTIVE_TRIP_STATUSES)).order_by(Trip.created_at.desc()).limit(1))


async def active_session_for_user(session: AsyncSession, user: User, lock: bool = False) -> DriverTrackingSession:
    if not user.driver_id:
        raise HTTPException(status_code=403, detail="This account is not linked to a driver profile.")
    query = select(DriverTrackingSession).where(DriverTrackingSession.driver_id == user.driver_id, DriverTrackingSession.status.in_(("ACTIVE", "PAUSED"))).order_by(DriverTrackingSession.started_at.desc()).limit(1)
    if lock:
        query = query.with_for_update()
    value = await session.scalar(query)
    if not value:
        raise HTTPException(status_code=409, detail="No active tracking session exists for this driver.")
    return value


def can_control_session(user: User, value: DriverTrackingSession) -> bool:
    return user.driver_id == value.driver_id or role_name(user) in ("Fleet Manager", "Administrator")


async def end_tracking_for_trip(session: AsyncSession, trip_id: str, reason: str, actor_id: str | None = None) -> None:
    sessions = (await session.scalars(select(DriverTrackingSession).where(DriverTrackingSession.trip_id == trip_id, DriverTrackingSession.status.in_(("ACTIVE", "PAUSED"))).with_for_update())).all()
    for value in sessions:
        before = session_value(value)
        value.status, value.ended_at, value.end_reason, value.updated_at = "ENDED", utc_now(), reason, utc_now()
        session.add(AuditEvent(id=f"audit-{uuid4().hex[:12]}", actor_id=actor_id, event_type="tracking.session.ended", target_type="tracking_session", target_id=value.id, before_state=before, after_state=session_value(value)))


async def end_tracking_for_driver(session: AsyncSession, driver_id: str, reason: str, actor_id: str | None = None) -> None:
    sessions = (await session.scalars(select(DriverTrackingSession).where(DriverTrackingSession.driver_id == driver_id, DriverTrackingSession.status.in_(("ACTIVE", "PAUSED"))).with_for_update())).all()
    for value in sessions:
        await end_tracking_for_trip(session, value.trip_id, reason, actor_id)


async def cleanup_expired_locations(session: AsyncSession) -> None:
    settings = await session.get(Preference, 1)
    retention_days = settings.tracking_raw_retention_days if settings else int(os.getenv("TRACKING_RAW_RETENTION_DAYS", "60"))
    await session.execute(delete(VehicleLocationPoint).where(VehicleLocationPoint.captured_at < utc_now() - timedelta(days=retention_days)))


async def authorize_vehicle(session: AsyncSession, user: User, vehicle: Vehicle, trip: Trip | None = None) -> None:
    role = role_name(user)
    if role in ("Fleet Manager", "Administrator"):
        return
    if role in ("Dispatcher", "Safety Officer") and (not user.region or user.region == vehicle.region):
        return
    if role == "Driver" and user.driver_id and trip and trip.driver_id == user.driver_id:
        return
    raise HTTPException(status_code=403, detail="You are not authorized to access this vehicle's location.")


async def snapshot_for_trip(session: AsyncSession, trip: Trip, settings: Preference, include_driver_name: bool = True) -> dict[str, Any]:
    vehicle = await session.get(Vehicle, trip.vehicle_id)
    driver = await session.get(Driver, trip.driver_id)
    latest = await session.get(LatestVehicleLocation, trip.vehicle_id)
    freshness, movement = tracking_state(latest, settings)
    remaining = None
    if latest and trip.destination_latitude is not None and trip.destination_longitude is not None:
        remaining = round(haversine_meters(latest.latitude, latest.longitude, trip.destination_latitude, trip.destination_longitude) / 1000, 1)
    return {
        "vehicle_id": vehicle.id,
        "vehicle_name": vehicle.name,
        "registration": vehicle.registration,
        "vehicle_type": vehicle.vehicle_type,
        "vehicle_status": vehicle.status,
        "region": vehicle.region,
        "depot": vehicle.depot,
        "driver_id": driver.id,
        "driver_name": driver.name if include_driver_name else None,
        "trip_id": trip.id,
        "trip_status": trip.status,
        "source": trip.source,
        "destination": trip.destination,
        "source_coordinates": [trip.source_latitude, trip.source_longitude] if trip.source_latitude is not None else None,
        "destination_coordinates": [trip.destination_latitude, trip.destination_longitude] if trip.destination_latitude is not None else None,
        "latitude": latest.latitude if latest else None,
        "longitude": latest.longitude if latest else None,
        "speed_mps": latest.speed_mps if latest else None,
        "heading_degrees": latest.heading_degrees if latest else None,
        "accuracy_meters": latest.accuracy_meters if latest else None,
        "captured_at": latest.captured_at.isoformat() if latest else None,
        "received_at": latest.received_at.isoformat() if latest else None,
        "freshness_status": freshness,
        "movement_status": movement,
        "remaining_distance_km": remaining,
        "distance_is_approximate": True,
    }


async def fleet_snapshots(session: AsyncSession, user: User, driver_visibility: bool = False) -> list[dict[str, Any]]:
    settings = await preferences(session)
    trips = (await session.scalars(select(Trip).where(Trip.status.in_(ACTIVE_TRIP_STATUSES)).order_by(Trip.created_at.desc()))).all()
    values: list[dict[str, Any]] = []
    for trip in trips:
        vehicle = await session.get(Vehicle, trip.vehicle_id)
        if role_name(user) in ("Dispatcher", "Safety Officer") and user.region and vehicle.region != user.region:
            continue
        if role_name(user) == "Driver":
            if not user.driver_id:
                continue
            visibility = settings.driver_fleet_visibility
            if visibility == "OWN_VEHICLE_ONLY" and trip.driver_id != user.driver_id:
                continue
            own_trip = await active_trip_for_driver(session, user.driver_id)
            if visibility == "SAME_TRIP_GROUP" and (not own_trip or trip.id != own_trip.id):
                continue
            own_driver = await session.get(Driver, user.driver_id)
            if visibility == "SAME_DEPOT_ACTIVE_VEHICLES" and own_driver and vehicle.depot != own_driver.depot:
                continue
            if visibility == "ALL_AUTHORIZED_ACTIVE_VEHICLES" and not settings.allow_driver_nearby_vehicles and trip.driver_id != user.driver_id:
                continue
        snapshot = await snapshot_for_trip(session, trip, settings, include_driver_name=not driver_visibility or trip.driver_id == user.driver_id)
        if role_name(user) == "Driver" and trip.driver_id != user.driver_id:
            if snapshot["latitude"] is not None:
                snapshot["latitude"] = round(snapshot["latitude"], 2)
                snapshot["longitude"] = round(snapshot["longitude"], 2)
                snapshot["accuracy_meters"] = max(snapshot["accuracy_meters"] or 0, 1000)
            snapshot["driver_id"] = None
        values.append(snapshot)
    return values


async def create_alert(session: AsyncSession, *, alert_type: str, message: str, deduplication_key: str, vehicle_id: str | None = None, driver_id: str | None = None, trip_id: str | None = None, severity: str = "WARNING") -> None:
    if await session.scalar(select(TrackingAlert.id).where(TrackingAlert.deduplication_key == deduplication_key)):
        return
    session.add(TrackingAlert(id=f"alert-{uuid4().hex[:10]}", vehicle_id=vehicle_id, driver_id=driver_id, trip_id=trip_id, alert_type=alert_type, severity=severity, message=message, deduplication_key=deduplication_key, created_at=utc_now()))


async def evaluate_geofences(session: AsyncSession, point: VehicleLocationPoint, vehicle: Vehicle) -> None:
    settings = await preferences(session)
    if not settings.geofence_alerts_enabled:
        return
    fences = (await session.scalars(select(Geofence).where(Geofence.is_active.is_(True), Geofence.depot_id == vehicle.depot))).all()
    for fence in fences:
        inside = haversine_meters(point.latitude, point.longitude, fence.center_latitude, fence.center_longitude) <= fence.radius_meters
        previous = await session.scalar(select(GeofenceEvent).where(GeofenceEvent.geofence_id == fence.id, GeofenceEvent.vehicle_id == point.vehicle_id).order_by(GeofenceEvent.detected_at.desc()).limit(1))
        previously_inside = previous is not None and previous.event_type in ("ENTERED", "DWELL_STARTED")
        event_type = "ENTERED" if inside and not previously_inside else "EXITED" if not inside and previously_inside else None
        if not event_type:
            continue
        event = GeofenceEvent(id=f"gfe-{uuid4().hex[:10]}", geofence_id=fence.id, vehicle_id=point.vehicle_id, driver_id=point.driver_id, trip_id=point.trip_id, event_type=event_type, detected_at=point.captured_at, latitude=point.latitude, longitude=point.longitude, event_metadata={"distance_meters": round(haversine_meters(point.latitude, point.longitude, fence.center_latitude, fence.center_longitude))})
        session.add(event)
        if event_type == "ENTERED" and fence.type == "CUSTOMER":
            await create_alert(session, alert_type="DESTINATION_REACHED", severity="INFO", message=f"{vehicle.name} entered {fence.name}.", deduplication_key=f"destination:{point.trip_id}:{fence.id}", vehicle_id=point.vehicle_id, driver_id=point.driver_id, trip_id=point.trip_id)
        if event_type == "ENTERED" and fence.type == "RESTRICTED":
            await create_alert(session, alert_type="RESTRICTED_AREA", severity="CRITICAL", message=f"{vehicle.name} entered restricted area {fence.name}.", deduplication_key=f"restricted:{point.trip_id}:{fence.id}", vehicle_id=point.vehicle_id, driver_id=point.driver_id, trip_id=point.trip_id)


@router.post("/tracking/sessions/start", status_code=201)
async def start_tracking(payload: StartTrackingInput, user: CurrentTrackingUser, session: Session) -> dict[str, Any]:
    if role_name(user) != "Driver" or not user.driver_id:
        raise HTTPException(status_code=403, detail="Only a linked driver account can start phone tracking.")
    settings = await preferences(session)
    if not settings.live_tracking_enabled:
        raise HTTPException(status_code=409, detail="Live tracking is disabled for this depot.")
    if not payload.consent:
        raise HTTPException(status_code=422, detail="Explicit location tracking consent is required.")
    trip = await active_trip_for_driver(session, user.driver_id)
    if not trip:
        raise HTTPException(status_code=409, detail="No dispatched or in-progress trip is assigned to this driver.")
    existing = await session.scalar(select(DriverTrackingSession).where(DriverTrackingSession.driver_id == user.driver_id, DriverTrackingSession.status.in_(("ACTIVE", "PAUSED"))).with_for_update())
    if existing:
        if existing.trip_id == trip.id:
            return session_value(existing)
        raise HTTPException(status_code=409, detail="End the existing tracking session before starting another trip.")
    now = utc_now()
    value = DriverTrackingSession(id=f"track-{uuid4().hex[:10]}", driver_id=trip.driver_id, vehicle_id=trip.vehicle_id, trip_id=trip.id, started_by_user_id=user.id, started_at=now, status="ACTIVE", consent_recorded_at=now, consent_version=payload.consent_version, start_reason="DRIVER_STARTED", created_at=now, updated_at=now)
    session.add(value)
    if trip.status == "Dispatched":
        trip.status = "In Progress"
    await audit(session, user, "tracking.session.started", "tracking_session", value.id, None, session_value(value))
    return session_value(value)


async def session_action(session_id: str, action: str, user: User, session: AsyncSession) -> dict[str, Any]:
    value = await session.scalar(select(DriverTrackingSession).where(DriverTrackingSession.id == session_id).with_for_update())
    if not value:
        raise HTTPException(status_code=404, detail="Tracking session not found.")
    if not can_control_session(user, value):
        raise HTTPException(status_code=403, detail="You cannot control this tracking session.")
    settings = await preferences(session)
    before = session_value(value)
    if action == "pause":
        if not settings.allow_driver_pause and role_name(user) == "Driver":
            raise HTTPException(status_code=403, detail="Driver pause is disabled by fleet policy.")
        if value.status != "ACTIVE":
            raise HTTPException(status_code=409, detail="Only an active session can be paused.")
        value.status = "PAUSED"
    elif action == "resume":
        if value.status != "PAUSED":
            raise HTTPException(status_code=409, detail="Only a paused session can be resumed.")
        value.status = "ACTIVE"
    else:
        if value.status not in ("ACTIVE", "PAUSED"):
            raise HTTPException(status_code=409, detail="This tracking session has already ended.")
        value.status, value.ended_at, value.end_reason = "ENDED", utc_now(), "DRIVER_ENDED" if role_name(user) == "Driver" else "MANAGER_ENDED"
        await create_alert(session, alert_type="TRACKING_ENDED", message="Tracking ended before trip completion.", deduplication_key=f"ended:{value.id}", vehicle_id=value.vehicle_id, driver_id=value.driver_id, trip_id=value.trip_id)
    value.updated_at = utc_now()
    await audit(session, user, f"tracking.session.{action}d" if action != "end" else "tracking.session.ended", "tracking_session", value.id, before, session_value(value))
    return session_value(value)


@router.post("/tracking/sessions/{session_id}/pause")
async def pause_tracking(session_id: str, user: CurrentTrackingUser, session: Session) -> dict[str, Any]:
    return await session_action(session_id, "pause", user, session)


@router.post("/tracking/sessions/{session_id}/resume")
async def resume_tracking(session_id: str, user: CurrentTrackingUser, session: Session) -> dict[str, Any]:
    return await session_action(session_id, "resume", user, session)


@router.post("/tracking/sessions/{session_id}/end")
async def end_tracking(session_id: str, user: CurrentTrackingUser, session: Session) -> dict[str, Any]:
    return await session_action(session_id, "end", user, session)


async def ingest_point(payload: LocationInput, user: User, session: AsyncSession) -> tuple[dict[str, Any], dict[str, Any] | None]:
    value = await active_session_for_user(session, user, lock=True)
    if value.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="Resume tracking before sending location points.")
    trip = await session.scalar(select(Trip).where(Trip.id == value.trip_id).with_for_update())
    if not trip or trip.status not in ACTIVE_TRIP_STATUSES or trip.driver_id != value.driver_id or trip.vehicle_id != value.vehicle_id:
        raise HTTPException(status_code=409, detail="The tracking assignment is no longer active.")
    if payload.captured_at > utc_now() + timedelta(minutes=5):
        raise HTTPException(status_code=422, detail="Location capture time cannot be in the future.")
    duplicate = await session.scalar(select(VehicleLocationPoint).where(VehicleLocationPoint.tracking_session_id == value.id, VehicleLocationPoint.source == "DRIVER_PHONE", VehicleLocationPoint.idempotency_key == payload.idempotency_key))
    if duplicate:
        return {"accepted": True, "duplicate": True, "id": duplicate.id}, None
    now = utc_now()
    metadata = {**(payload.metadata or {}), "battery_percentage": payload.battery_percentage, "network_state": payload.network_state}
    point = VehicleLocationPoint(id=f"loc-{uuid4().hex[:12]}", tracking_session_id=value.id, driver_id=value.driver_id, vehicle_id=value.vehicle_id, trip_id=value.trip_id, latitude=payload.latitude, longitude=payload.longitude, accuracy_meters=payload.accuracy_meters, altitude=payload.altitude, altitude_accuracy=payload.altitude_accuracy, heading_degrees=payload.heading_degrees, speed_mps=payload.speed_mps, captured_at=payload.captured_at, received_at=now, source="DRIVER_PHONE", idempotency_key=payload.idempotency_key, is_mock_location=payload.is_mock_location, location_metadata=metadata)
    session.add(point)
    value.last_location_at, value.updated_at = payload.captured_at, now
    latest = await session.get(LatestVehicleLocation, value.vehicle_id)
    if not latest:
        latest = LatestVehicleLocation(vehicle_id=value.vehicle_id, trip_id=value.trip_id, driver_id=value.driver_id, tracking_session_id=value.id, latitude=payload.latitude, longitude=payload.longitude, speed_mps=payload.speed_mps, heading_degrees=payload.heading_degrees, accuracy_meters=payload.accuracy_meters, captured_at=payload.captured_at, received_at=now, freshness_status="ONLINE")
        session.add(latest)
    elif payload.captured_at >= latest.captured_at:
        latest.trip_id, latest.driver_id, latest.tracking_session_id = value.trip_id, value.driver_id, value.id
        latest.latitude, latest.longitude, latest.speed_mps, latest.heading_degrees = payload.latitude, payload.longitude, payload.speed_mps, payload.heading_degrees
        latest.accuracy_meters, latest.captured_at, latest.received_at, latest.freshness_status = payload.accuracy_meters, payload.captured_at, now, "ONLINE"
    vehicle = await session.get(Vehicle, value.vehicle_id)
    await evaluate_geofences(session, point, vehicle)
    event = {"type": "vehicle_location", "vehicle_id": value.vehicle_id, "trip_id": value.trip_id, "latitude": payload.latitude, "longitude": payload.longitude, "speed_mps": payload.speed_mps, "accuracy_meters": payload.accuracy_meters, "captured_at": payload.captured_at.isoformat()}
    return {"accepted": True, "duplicate": False, "id": point.id}, event


@router.post("/tracking/locations", status_code=202)
async def submit_location(payload: LocationInput, background_tasks: BackgroundTasks, user: CurrentTrackingUser, session: Session) -> dict[str, Any]:
    ensure_rate_limit(user.id)
    result, event = await ingest_point(payload, user, session)
    if event:
        background_tasks.add_task(broker.publish, event)
    return result


@router.post("/tracking/locations/batch", status_code=202)
async def submit_location_batch(payload: LocationBatchInput, background_tasks: BackgroundTasks, user: CurrentTrackingUser, session: Session) -> dict[str, Any]:
    ensure_rate_limit(user.id, len(payload.points))
    results, events = [], []
    for point in sorted(payload.points, key=lambda item: item.captured_at):
        result, event = await ingest_point(point, user, session)
        results.append(result)
        if event:
            events.append(event)
    for event in events:
        background_tasks.add_task(broker.publish, event)
    return {"accepted": len(results), "duplicates": sum(bool(result.get("duplicate")) for result in results), "results": results}


@router.get("/tracking/fleet/latest")
async def latest_fleet(user: CurrentTrackingUser, session: Session) -> list[dict[str, Any]]:
    require_permission(user, "tracking.view_all" if role_name(user) in ("Fleet Manager", "Administrator") else "tracking.view_depot")
    snapshots = await fleet_snapshots(session, user)
    for snapshot in snapshots:
        if snapshot["freshness_status"] in ("STALE", "OFFLINE"):
            await create_alert(session, alert_type=f"VEHICLE_{snapshot['freshness_status']}", message=f"{snapshot['vehicle_name']} location is {snapshot['freshness_status'].lower()}.", deduplication_key=f"freshness:{snapshot['trip_id']}:{snapshot['freshness_status']}", vehicle_id=snapshot["vehicle_id"], driver_id=snapshot["driver_id"], trip_id=snapshot["trip_id"])
        if snapshot["movement_status"] == "STOPPED" and snapshot["freshness_status"] != "OFFLINE":
            await create_alert(session, alert_type="LONG_STOP", message=f"{snapshot['vehicle_name']} has reported a prolonged stop.", deduplication_key=f"long-stop:{snapshot['trip_id']}", vehicle_id=snapshot["vehicle_id"], driver_id=snapshot["driver_id"], trip_id=snapshot["trip_id"])
    return snapshots


@router.get("/tracking/config")
async def tracking_config(user: CurrentTrackingUser, session: Session) -> dict[str, Any]:
    if role_name(user) not in (*TRACKING_VIEW_ROLES, "Driver"):
        raise HTTPException(status_code=403, detail="Tracking configuration is not available to this role.")
    settings = await preferences(session)
    return {"map_provider": settings.map_provider, "directions_provider": settings.directions_provider, "stale_seconds": settings.tracking_stale_seconds, "offline_seconds": settings.tracking_offline_seconds, "permissions": sorted(ROLE_TRACKING_PERMISSIONS.get(role_name(user), set()))}


@router.get("/tracking/my-visible-fleet")
async def my_visible_fleet(user: CurrentTrackingUser, session: Session) -> list[dict[str, Any]]:
    if role_name(user) != "Driver":
        raise HTTPException(status_code=403, detail="This endpoint is for linked driver accounts.")
    return await fleet_snapshots(session, user, driver_visibility=True)


@router.get("/tracking/my-active-trip")
async def my_active_trip(user: CurrentTrackingUser, session: Session) -> dict[str, Any]:
    if role_name(user) != "Driver" or not user.driver_id:
        raise HTTPException(status_code=403, detail="This endpoint is for linked driver accounts.")
    trip = await active_trip_for_driver(session, user.driver_id)
    if not trip:
        raise HTTPException(status_code=404, detail="No active trip is assigned to this driver.")
    settings = await preferences(session)
    vehicle = await session.get(Vehicle, trip.vehicle_id)
    driver = await session.get(Driver, trip.driver_id)
    active_session = await session.scalar(select(DriverTrackingSession).where(DriverTrackingSession.driver_id == user.driver_id, DriverTrackingSession.status.in_(("ACTIVE", "PAUSED"))).order_by(DriverTrackingSession.started_at.desc()).limit(1))
    return {"trip": {"id": trip.id, "status": trip.status, "source": trip.source, "destination": trip.destination, "planned_distance_km": trip.planned_distance_km, "source_coordinates": [trip.source_latitude, trip.source_longitude] if trip.source_latitude is not None else None, "destination_coordinates": [trip.destination_latitude, trip.destination_longitude] if trip.destination_latitude is not None else None}, "vehicle": {"id": vehicle.id, "name": vehicle.name, "registration": vehicle.registration}, "driver": {"id": driver.id, "name": driver.name}, "tracking_session": session_value(active_session) if active_session else None, "settings": {"update_interval_seconds": settings.tracking_update_interval_seconds, "stationary_interval_seconds": settings.tracking_stationary_interval_seconds, "minimum_movement_meters": settings.tracking_minimum_movement_meters, "allow_pause": settings.allow_driver_pause, "map_provider": settings.map_provider, "directions_provider": settings.directions_provider}}


async def authorized_history(session: AsyncSession, user: User, *, vehicle_id: str | None = None, trip_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    query = select(VehicleLocationPoint)
    trip = None
    if vehicle_id:
        vehicle = await session.get(Vehicle, vehicle_id)
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found.")
        trip = await session.scalar(select(Trip).where(Trip.vehicle_id == vehicle_id).order_by(Trip.created_at.desc()).limit(1))
        await authorize_vehicle(session, user, vehicle, trip)
        query = query.where(VehicleLocationPoint.vehicle_id == vehicle_id)
    if trip_id:
        trip = await session.get(Trip, trip_id)
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found.")
        vehicle = await session.get(Vehicle, trip.vehicle_id)
        await authorize_vehicle(session, user, vehicle, trip)
        query = query.where(VehicleLocationPoint.trip_id == trip_id)
    points = (await session.scalars(query.order_by(VehicleLocationPoint.captured_at.desc()).limit(limit))).all()
    await audit(session, user, "tracking.history.viewed", "trip" if trip_id else "vehicle", trip_id or vehicle_id or "unknown", None, {"points_returned": len(points)})
    return [{"id": point.id, "latitude": point.latitude, "longitude": point.longitude, "accuracy_meters": point.accuracy_meters, "speed_mps": point.speed_mps, "heading_degrees": point.heading_degrees, "captured_at": point.captured_at.isoformat(), "source": point.source} for point in reversed(points)]


@router.get("/tracking/vehicles/{vehicle_id}/latest")
async def vehicle_latest(vehicle_id: str, user: CurrentTrackingUser, session: Session) -> dict[str, Any]:
    trip = await session.scalar(select(Trip).where(Trip.vehicle_id == vehicle_id, Trip.status.in_(ACTIVE_TRIP_STATUSES)).order_by(Trip.created_at.desc()).limit(1))
    if not trip:
        raise HTTPException(status_code=404, detail="No active tracked trip exists for this vehicle.")
    vehicle = await session.get(Vehicle, vehicle_id)
    await authorize_vehicle(session, user, vehicle, trip)
    return await snapshot_for_trip(session, trip, await preferences(session), include_driver_name=role_name(user) != "Driver" or trip.driver_id == user.driver_id)


@router.get("/tracking/vehicles/{vehicle_id}/history")
async def vehicle_history(vehicle_id: str, user: CurrentTrackingUser, session: Session, limit: int = Query(default=200, ge=1, le=500)) -> list[dict[str, Any]]:
    return await authorized_history(session, user, vehicle_id=vehicle_id, limit=limit)


@router.get("/tracking/trips/{trip_id}/history")
async def trip_history(trip_id: str, user: CurrentTrackingUser, session: Session, limit: int = Query(default=200, ge=1, le=500)) -> list[dict[str, Any]]:
    return await authorized_history(session, user, trip_id=trip_id, limit=limit)


@router.get("/tracking/trips/{trip_id}/route-progress")
async def route_progress(trip_id: str, user: CurrentTrackingUser, session: Session) -> dict[str, Any]:
    trip = await session.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found.")
    vehicle = await session.get(Vehicle, trip.vehicle_id)
    await authorize_vehicle(session, user, vehicle, trip)
    snapshot = await snapshot_for_trip(session, trip, await preferences(session))
    if snapshot["remaining_distance_km"] is None:
        return {"trip_id": trip.id, "progress_percent": None, "remaining_distance_km": None, "approximate": True}
    progress = max(0, min(100, round((1 - snapshot["remaining_distance_km"] / trip.planned_distance_km) * 100))) if trip.planned_distance_km else None
    return {"trip_id": trip.id, "progress_percent": progress, "remaining_distance_km": snapshot["remaining_distance_km"], "approximate": True}


@router.get("/tracking/trips/{trip_id}/route")
async def trip_route(trip_id: str, user: CurrentTrackingUser, session: Session) -> dict[str, Any]:
    trip = await session.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found.")
    vehicle = await session.get(Vehicle, trip.vehicle_id)
    await authorize_vehicle(session, user, vehicle, trip)
    if None in (trip.source_latitude, trip.source_longitude, trip.destination_latitude, trip.destination_longitude):
        raise HTTPException(status_code=422, detail="This trip does not have route coordinates.")
    selected_provider = (await preferences(session)).directions_provider
    cache_key = f"{trip.id}:{trip.source_latitude}:{trip.source_longitude}:{trip.destination_latitude}:{trip.destination_longitude}:{selected_provider}"
    result = route_cache.get(cache_key)
    if not result:
        try:
            result = await directions_provider(selected_provider).route((trip.source_latitude, trip.source_longitude), (trip.destination_latitude, trip.destination_longitude))
        except Exception:
            fallback = await StraightLineDirectionsProvider().route((trip.source_latitude, trip.source_longitude), (trip.destination_latitude, trip.destination_longitude))
            result = RouteResult(**{**fallback.__dict__, "warning": "Configured directions provider was unavailable; displaying an approximate straight-line route."})
        route_cache[cache_key] = result
    return {"trip_id": trip.id, "coordinates": result.coordinates, "distance_km": result.distance_km, "duration_minutes": result.duration_minutes, "provider": result.provider, "approximate": result.approximate, "warning": result.warning}


@router.get("/tracking/alerts")
async def tracking_alerts(user: CurrentTrackingUser, session: Session, limit: int = Query(default=30, ge=1, le=100)) -> list[dict[str, Any]]:
    require_roles(user, *TRACKING_VIEW_ROLES)
    alerts = (await session.scalars(select(TrackingAlert).where(TrackingAlert.resolved_at.is_(None)).order_by(TrackingAlert.created_at.desc()).limit(limit))).all()
    return [{"id": value.id, "vehicle_id": value.vehicle_id, "trip_id": value.trip_id, "alert_type": value.alert_type, "severity": value.severity, "message": value.message, "created_at": value.created_at.isoformat()} for value in alerts]


@router.post("/tracking/issues", status_code=201)
async def report_tracking_issue(payload: TrackingIssueInput, user: CurrentTrackingUser, session: Session) -> dict[str, Any]:
    if role_name(user) != "Driver" or not user.driver_id:
        raise HTTPException(status_code=403, detail="Only a linked driver can report a live-trip issue here.")
    trip = await active_trip_for_driver(session, user.driver_id)
    if not trip:
        raise HTTPException(status_code=409, detail="No active trip is assigned to this driver.")
    alert_id = f"alert-{uuid4().hex[:10]}"
    value = TrackingAlert(id=alert_id, vehicle_id=trip.vehicle_id, driver_id=trip.driver_id, trip_id=trip.id, alert_type=payload.issue_type, severity="CRITICAL" if payload.issue_type == "DRIVER_EMERGENCY" else "WARNING", message=payload.message, deduplication_key=f"driver-issue:{uuid4().hex}", created_at=utc_now())
    session.add(value)
    await audit(session, user, "tracking.issue.reported", "tracking_alert", value.id, None, {"issue_type": payload.issue_type, "trip_id": trip.id})
    return {"id": value.id, "status": "reported"}


@router.get("/tracking/events")
async def tracking_events(user: CurrentTrackingUser) -> StreamingResponse:
    if role_name(user) not in (*TRACKING_VIEW_ROLES, "Driver"):
        raise HTTPException(status_code=403, detail="Live tracking events are not available to this role.")

    async def stream() -> AsyncIterator[str]:
        async for event in broker.subscribe():
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def geofence_value(value: Geofence) -> dict[str, Any]:
    return {"id": value.id, "depot_id": value.depot_id, "name": value.name, "type": value.type, "center_latitude": value.center_latitude, "center_longitude": value.center_longitude, "radius_meters": value.radius_meters, "polygon_geojson": value.polygon_geojson, "is_active": value.is_active}


@router.get("/geofences")
async def list_geofences(user: CurrentTrackingUser, session: Session) -> list[dict[str, Any]]:
    require_roles(user, *TRACKING_VIEW_ROLES)
    query = select(Geofence).order_by(Geofence.name)
    fences = (await session.scalars(query)).all()
    return [geofence_value(value) for value in fences if role_name(user) in ("Fleet Manager", "Administrator") or not user.region or user.region.lower() in value.depot_id.lower()]


@router.post("/geofences", status_code=201)
async def create_geofence(payload: GeofenceInput, user: CurrentTrackingUser, session: Session) -> dict[str, Any]:
    require_roles(user, *TRACKING_MANAGE_ROLES)
    value = Geofence(id=f"geo-{uuid4().hex[:10]}", created_by=user.id, created_at=utc_now(), updated_at=utc_now(), **payload.model_dump())
    session.add(value)
    await audit(session, user, "geofence.created", "geofence", value.id, None, geofence_value(value))
    return geofence_value(value)


@router.patch("/geofences/{geofence_id}")
async def update_geofence(geofence_id: str, payload: GeofenceInput, user: CurrentTrackingUser, session: Session) -> dict[str, Any]:
    require_roles(user, *TRACKING_MANAGE_ROLES)
    value = await session.scalar(select(Geofence).where(Geofence.id == geofence_id).with_for_update())
    if not value:
        raise HTTPException(status_code=404, detail="Geofence not found.")
    before = geofence_value(value)
    for field, field_value in payload.model_dump().items():
        setattr(value, field, field_value)
    value.updated_at = utc_now()
    await audit(session, user, "geofence.updated", "geofence", value.id, before, geofence_value(value))
    return geofence_value(value)


@router.delete("/geofences/{geofence_id}", status_code=204, response_class=Response)
async def delete_geofence(geofence_id: str, user: CurrentTrackingUser, session: Session) -> Response:
    require_roles(user, *TRACKING_MANAGE_ROLES)
    value = await session.scalar(select(Geofence).where(Geofence.id == geofence_id).with_for_update())
    if not value:
        raise HTTPException(status_code=404, detail="Geofence not found.")
    before = geofence_value(value)
    value.is_active = False
    await audit(session, user, "geofence.deactivated", "geofence", value.id, before, geofence_value(value))
    return Response(status_code=204)
