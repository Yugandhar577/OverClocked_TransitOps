from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import CheckConstraint, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text
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
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Available", index=True)


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
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Active", index=True)
    opened_at: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    closed_at: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")


class FuelLog(Base):
    __tablename__ = "fuel_logs"
    __table_args__ = (
        CheckConstraint("liters > 0", name="ck_fuel_liters_positive"),
        CheckConstraint("cost > 0", name="ck_fuel_cost_positive"),
        CheckConstraint("odometer_km >= 0", name="ck_fuel_odometer_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"), nullable=False, index=True)
    trip_id: Mapped[str | None] = mapped_column(ForeignKey("trips.id"), index=True)
    logged_at: Mapped[date] = mapped_column("date", Date, nullable=False, default=date.today)
    liters: Mapped[float] = mapped_column(Float, nullable=False)
    cost: Mapped[float] = mapped_column(Float, nullable=False)
    odometer_km: Mapped[float] = mapped_column(Float, nullable=False)
    vendor: Mapped[str] = mapped_column(String(80), nullable=False, default="")


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
