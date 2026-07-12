from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    users: Mapped[list[User]] = relationship(back_populates="role")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id"), nullable=False)
    driver_id: Mapped[str | None] = mapped_column(ForeignKey("drivers.id"), unique=True)
    region: Mapped[str | None] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    role: Mapped[Role] = relationship(back_populates="users", lazy="joined")


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        CheckConstraint("capacity_kg >= 0", name="ck_vehicles_capacity_nonnegative"),
        CheckConstraint("odometer_km >= 0", name="ck_vehicles_odometer_nonnegative"),
        CheckConstraint("acquisition_cost >= 0", name="ck_vehicles_acquisition_cost_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    registration: Mapped[str] = mapped_column(String(32), nullable=False)
    registration_normalized: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(40), nullable=False)
    capacity_kg: Mapped[float] = mapped_column(Float, nullable=False)
    odometer_km: Mapped[float] = mapped_column(Float, nullable=False)
    acquisition_cost: Mapped[float] = mapped_column(Float, nullable=False)
    region: Mapped[str] = mapped_column(String(80), nullable=False, default="Ahmedabad")
    depot: Mapped[str] = mapped_column(String(100), nullable=False, default="Ahmedabad Depot")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Available", index=True)
    brand: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    vin: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    fuel_type: Mapped[str] = mapped_column(String(20), nullable=False, default="Diesel")
    manufacture_year: Mapped[int | None] = mapped_column(Integer)
    color: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    photo_url: Mapped[str] = mapped_column(Text, nullable=False, default="")


class Driver(Base):
    __tablename__ = "drivers"
    __table_args__ = (CheckConstraint("safety_score >= 0 AND safety_score <= 100", name="ck_drivers_safety_score"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    license_number: Mapped[str] = mapped_column(String(32), nullable=False)
    license_normalized: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    license_category: Mapped[str] = mapped_column(String(20), nullable=False)
    license_expiry: Mapped[date] = mapped_column(Date, nullable=False)
    contact: Mapped[str] = mapped_column(String(30), nullable=False)
    safety_score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Available", index=True)
    region: Mapped[str] = mapped_column(String(80), nullable=False, default="Ahmedabad")
    depot: Mapped[str] = mapped_column(String(100), nullable=False, default="Ahmedabad Depot")


class Trip(Base):
    __tablename__ = "trips"
    __table_args__ = (
        CheckConstraint("cargo_kg > 0", name="ck_trips_cargo_positive"),
        CheckConstraint("planned_distance_km > 0", name="ck_trips_distance_positive"),
        CheckConstraint("revenue >= 0", name="ck_trips_revenue_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    destination: Mapped[str] = mapped_column(String(80), nullable=False)
    source_latitude: Mapped[float | None] = mapped_column(Float)
    source_longitude: Mapped[float | None] = mapped_column(Float)
    destination_latitude: Mapped[float | None] = mapped_column(Float)
    destination_longitude: Mapped[float | None] = mapped_column(Float)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"), nullable=False, index=True)
    driver_id: Mapped[str] = mapped_column(ForeignKey("drivers.id"), nullable=False, index=True)
    cargo_kg: Mapped[float] = mapped_column(Float, nullable=False)
    planned_distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    actual_distance_km: Mapped[float | None] = mapped_column(Float)
    revenue: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancellation_reason: Mapped[str | None] = mapped_column(String(500))


class Maintenance(Base):
    __tablename__ = "maintenance"
    __table_args__ = (CheckConstraint("cost >= 0", name="ck_maintenance_cost_nonnegative"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"), nullable=False, index=True)
    service_type: Mapped[str] = mapped_column(String(80), nullable=False)
    cost: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Scheduled", index=True)
    opened_at: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    closed_at: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    vendor: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    odometer_km: Mapped[float | None] = mapped_column(Float)
    invoice_reference: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="Normal", index=True)
    due_date: Mapped[date | None] = mapped_column(Date)


class VehicleDocument(Base):
    __tablename__ = "vehicle_documents"
    __table_args__ = (CheckConstraint("cost >= 0", name="ck_vehicle_documents_cost_nonnegative"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    reference_number: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    provider: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    cost: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Active", index=True)


class OdometerLog(Base):
    __tablename__ = "odometer_logs"
    __table_args__ = (CheckConstraint("value_km >= 0", name="ck_odometer_logs_value_nonnegative"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"), nullable=False, index=True)
    logged_at: Mapped[date] = mapped_column("date", Date, nullable=False, default=date.today, index=True)
    value_km: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    driver_id: Mapped[str | None] = mapped_column(ForeignKey("drivers.id"), index=True)


class FuelLog(Base):
    __tablename__ = "fuel_logs"
    __table_args__ = (
        CheckConstraint("liters > 0", name="ck_fuel_liters_positive"),
        CheckConstraint("cost > 0", name="ck_fuel_cost_positive"),
        CheckConstraint("price_per_liter > 0", name="ck_fuel_price_per_liter_positive"),
        CheckConstraint("odometer_km >= 0", name="ck_fuel_odometer_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"), nullable=False, index=True)
    trip_id: Mapped[str | None] = mapped_column(ForeignKey("trips.id"), index=True)
    logged_at: Mapped[date] = mapped_column("date", Date, nullable=False, default=date.today)
    liters: Mapped[float] = mapped_column(Float, nullable=False)
    cost: Mapped[float] = mapped_column(Float, nullable=False)
    price_per_liter: Mapped[float] = mapped_column(Float, nullable=False)
    odometer_km: Mapped[float] = mapped_column(Float, nullable=False)
    vendor: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    receipt_image: Mapped[str | None] = mapped_column(String(512))


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    vehicle_id: Mapped[str | None] = mapped_column(ForeignKey("vehicles.id"), index=True)
    trip_id: Mapped[str | None] = mapped_column(ForeignKey("trips.id"), index=True)
    logged_at: Mapped[date] = mapped_column("date", Date, nullable=False, default=date.today)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")


class Preference(Base):
    __tablename__ = "preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    depot_name: Mapped[str] = mapped_column(String(100), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    distance_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    live_tracking_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tracking_update_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    tracking_stationary_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=25)
    tracking_minimum_movement_meters: Mapped[float] = mapped_column(Float, nullable=False, default=20)
    tracking_stale_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    tracking_offline_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=180)
    tracking_raw_retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    driver_fleet_visibility: Mapped[str] = mapped_column(String(40), nullable=False, default="OWN_VEHICLE_ONLY")
    allow_driver_pause: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_driver_nearby_vehicles: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    map_provider: Mapped[str] = mapped_column(String(40), nullable=False, default="openstreetmap")
    directions_provider: Mapped[str] = mapped_column(String(40), nullable=False, default="straight_line")
    geofence_alerts_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    license_expiry_warning_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    license_expiry_critical_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    before_state: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_state: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class DriverTrackingSession(Base):
    __tablename__ = "driver_tracking_sessions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    driver_id: Mapped[str] = mapped_column(ForeignKey("drivers.id"), nullable=False, index=True)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"), nullable=False, index=True)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id"), nullable=False, index=True)
    started_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True)
    consent_recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    consent_version: Mapped[str] = mapped_column(String(20), nullable=False)
    start_reason: Mapped[str] = mapped_column(String(100), nullable=False, default="DRIVER_STARTED")
    end_reason: Mapped[str | None] = mapped_column(String(100))
    last_location_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class VehicleLocationPoint(Base):
    __tablename__ = "vehicle_location_points"
    __table_args__ = (
        UniqueConstraint("tracking_session_id", "source", "idempotency_key", name="uq_location_session_source_key"),
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_location_latitude"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_location_longitude"),
        CheckConstraint("accuracy_meters >= 0", name="ck_location_accuracy"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tracking_session_id: Mapped[str] = mapped_column(ForeignKey("driver_tracking_sessions.id"), nullable=False, index=True)
    driver_id: Mapped[str] = mapped_column(ForeignKey("drivers.id"), nullable=False, index=True)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"), nullable=False, index=True)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id"), nullable=False, index=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy_meters: Mapped[float] = mapped_column(Float, nullable=False)
    altitude: Mapped[float | None] = mapped_column(Float)
    altitude_accuracy: Mapped[float | None] = mapped_column(Float)
    heading_degrees: Mapped[float | None] = mapped_column(Float)
    speed_mps: Mapped[float | None] = mapped_column(Float)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="DRIVER_PHONE")
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    is_mock_location: Mapped[bool | None] = mapped_column(Boolean)
    location_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)


class LatestVehicleLocation(Base):
    __tablename__ = "latest_vehicle_locations"

    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"), primary_key=True)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id"), nullable=False, index=True)
    driver_id: Mapped[str] = mapped_column(ForeignKey("drivers.id"), nullable=False, index=True)
    tracking_session_id: Mapped[str] = mapped_column(ForeignKey("driver_tracking_sessions.id"), nullable=False, index=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    speed_mps: Mapped[float | None] = mapped_column(Float)
    heading_degrees: Mapped[float | None] = mapped_column(Float)
    accuracy_meters: Mapped[float] = mapped_column(Float, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    freshness_status: Mapped[str] = mapped_column(String(30), nullable=False, default="ONLINE")


class Geofence(Base):
    __tablename__ = "geofences"
    __table_args__ = (
        CheckConstraint("center_latitude >= -90 AND center_latitude <= 90", name="ck_geofence_latitude"),
        CheckConstraint("center_longitude >= -180 AND center_longitude <= 180", name="ck_geofence_longitude"),
        CheckConstraint("radius_meters > 0", name="ck_geofence_radius"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    depot_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    center_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    center_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    radius_meters: Mapped[float] = mapped_column(Float, nullable=False)
    polygon_geojson: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class GeofenceEvent(Base):
    __tablename__ = "geofence_events"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    geofence_id: Mapped[str] = mapped_column(ForeignKey("geofences.id"), nullable=False, index=True)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"), nullable=False, index=True)
    driver_id: Mapped[str] = mapped_column(ForeignKey("drivers.id"), nullable=False, index=True)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)


class TrackingAlert(Base):
    __tablename__ = "tracking_alerts"
    __table_args__ = (UniqueConstraint("deduplication_key", name="uq_tracking_alert_deduplication_key"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    vehicle_id: Mapped[str | None] = mapped_column(ForeignKey("vehicles.id"), index=True)
    driver_id: Mapped[str | None] = mapped_column(ForeignKey("drivers.id"), index=True)
    trip_id: Mapped[str | None] = mapped_column(ForeignKey("trips.id"), index=True)
    alert_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="WARNING")
    message: Mapped[str] = mapped_column(String(300), nullable=False)
    deduplication_key: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
