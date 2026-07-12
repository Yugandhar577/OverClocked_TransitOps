"""Create the TransitOps operational database schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-12 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("roles", sa.Column("id", sa.String(40), primary_key=True), sa.Column("name", sa.String(40), nullable=False, unique=True))
    op.create_table("users", sa.Column("id", sa.String(40), primary_key=True), sa.Column("name", sa.String(80), nullable=False), sa.Column("email", sa.String(254), nullable=False, unique=True), sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("role_id", sa.String(40), sa.ForeignKey("roles.id"), nullable=False), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table("vehicles", sa.Column("id", sa.String(40), primary_key=True), sa.Column("registration", sa.String(32), nullable=False), sa.Column("registration_normalized", sa.String(32), nullable=False, unique=True), sa.Column("name", sa.String(80), nullable=False), sa.Column("vehicle_type", sa.String(40), nullable=False), sa.Column("capacity_kg", sa.Float(), nullable=False), sa.Column("odometer_km", sa.Float(), nullable=False), sa.Column("acquisition_cost", sa.Float(), nullable=False), sa.Column("region", sa.String(80), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.CheckConstraint("capacity_kg >= 0", name="ck_vehicles_capacity_nonnegative"), sa.CheckConstraint("odometer_km >= 0", name="ck_vehicles_odometer_nonnegative"), sa.CheckConstraint("acquisition_cost >= 0", name="ck_vehicles_acquisition_cost_nonnegative"))
    op.create_index("ix_vehicles_status", "vehicles", ["status"])

    op.create_table("drivers", sa.Column("id", sa.String(40), primary_key=True), sa.Column("name", sa.String(80), nullable=False), sa.Column("license_number", sa.String(32), nullable=False), sa.Column("license_normalized", sa.String(32), nullable=False, unique=True), sa.Column("license_category", sa.String(20), nullable=False), sa.Column("license_expiry", sa.Date(), nullable=False), sa.Column("contact", sa.String(30), nullable=False), sa.Column("safety_score", sa.Float(), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("region", sa.String(80), nullable=False), sa.CheckConstraint("safety_score >= 0 AND safety_score <= 100", name="ck_drivers_safety_score"))
    op.create_index("ix_drivers_status", "drivers", ["status"])

    op.create_table("trips", sa.Column("id", sa.String(40), primary_key=True), sa.Column("source", sa.String(80), nullable=False), sa.Column("destination", sa.String(80), nullable=False), sa.Column("vehicle_id", sa.String(40), sa.ForeignKey("vehicles.id"), nullable=False), sa.Column("driver_id", sa.String(40), sa.ForeignKey("drivers.id"), nullable=False), sa.Column("cargo_kg", sa.Float(), nullable=False), sa.Column("planned_distance_km", sa.Float(), nullable=False), sa.Column("actual_distance_km", sa.Float()), sa.Column("revenue", sa.Float(), nullable=False, server_default="0"), sa.Column("notes", sa.Text(), nullable=False, server_default=""), sa.Column("status", sa.String(20), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("completed_at", sa.DateTime()), sa.Column("cancellation_reason", sa.String(500)), sa.CheckConstraint("cargo_kg > 0", name="ck_trips_cargo_positive"), sa.CheckConstraint("planned_distance_km > 0", name="ck_trips_distance_positive"), sa.CheckConstraint("revenue >= 0", name="ck_trips_revenue_nonnegative"))
    op.create_index("ix_trips_vehicle_id", "trips", ["vehicle_id"])
    op.create_index("ix_trips_driver_id", "trips", ["driver_id"])
    op.create_index("ix_trips_status", "trips", ["status"])

    op.create_table("maintenance", sa.Column("id", sa.String(40), primary_key=True), sa.Column("vehicle_id", sa.String(40), sa.ForeignKey("vehicles.id"), nullable=False), sa.Column("service_type", sa.String(80), nullable=False), sa.Column("cost", sa.Float(), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("opened_at", sa.Date(), nullable=False), sa.Column("closed_at", sa.Date()), sa.Column("notes", sa.Text(), nullable=False, server_default=""), sa.CheckConstraint("cost >= 0", name="ck_maintenance_cost_nonnegative"))
    op.create_index("ix_maintenance_vehicle_id", "maintenance", ["vehicle_id"])
    op.create_index("ix_maintenance_status", "maintenance", ["status"])

    op.create_table("fuel_logs", sa.Column("id", sa.String(40), primary_key=True), sa.Column("vehicle_id", sa.String(40), sa.ForeignKey("vehicles.id"), nullable=False), sa.Column("trip_id", sa.String(40), sa.ForeignKey("trips.id")), sa.Column("date", sa.Date(), nullable=False), sa.Column("liters", sa.Float(), nullable=False), sa.Column("cost", sa.Float(), nullable=False), sa.Column("odometer_km", sa.Float(), nullable=False), sa.Column("vendor", sa.String(80), nullable=False, server_default=""), sa.CheckConstraint("liters > 0", name="ck_fuel_liters_positive"), sa.CheckConstraint("cost > 0", name="ck_fuel_cost_positive"), sa.CheckConstraint("odometer_km >= 0", name="ck_fuel_odometer_nonnegative"))
    op.create_index("ix_fuel_logs_vehicle_id", "fuel_logs", ["vehicle_id"])
    op.create_index("ix_fuel_logs_trip_id", "fuel_logs", ["trip_id"])

    op.create_table("expenses", sa.Column("id", sa.String(40), primary_key=True), sa.Column("category", sa.String(20), nullable=False), sa.Column("amount", sa.Float(), nullable=False), sa.Column("vehicle_id", sa.String(40), sa.ForeignKey("vehicles.id")), sa.Column("trip_id", sa.String(40), sa.ForeignKey("trips.id")), sa.Column("date", sa.Date(), nullable=False), sa.Column("notes", sa.Text(), nullable=False, server_default=""), sa.CheckConstraint("amount > 0", name="ck_expenses_amount_positive"))
    op.create_index("ix_expenses_vehicle_id", "expenses", ["vehicle_id"])
    op.create_index("ix_expenses_trip_id", "expenses", ["trip_id"])

    op.create_table("preferences", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("depot_name", sa.String(100), nullable=False), sa.Column("currency", sa.String(8), nullable=False), sa.Column("distance_unit", sa.String(20), nullable=False))
    op.create_table("audit_events", sa.Column("id", sa.String(40), primary_key=True), sa.Column("actor_id", sa.String(40), sa.ForeignKey("users.id")), sa.Column("event_type", sa.String(80), nullable=False), sa.Column("target_type", sa.String(40), nullable=False), sa.Column("target_id", sa.String(40), nullable=False), sa.Column("occurred_at", sa.DateTime(), nullable=False), sa.Column("before_state", sa.JSON()), sa.Column("after_state", sa.JSON()))
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"])
    op.create_index("ix_audit_events_target_id", "audit_events", ["target_id"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("preferences")
    op.drop_table("expenses")
    op.drop_table("fuel_logs")
    op.drop_table("maintenance")
    op.drop_table("trips")
    op.drop_table("drivers")
    op.drop_table("vehicles")
    op.drop_table("users")
    op.drop_table("roles")
