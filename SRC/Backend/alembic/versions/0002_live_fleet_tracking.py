"""Add production-oriented live fleet tracking.

Revision ID: 0002_live_fleet_tracking
Revises: 0001_initial_schema
Create Date: 2026-07-12 12:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_live_fleet_tracking"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("driver_id", sa.String(40), nullable=True))
    op.add_column("users", sa.Column("region", sa.String(80), nullable=True))
    op.create_foreign_key("fk_users_driver_id", "users", "drivers", ["driver_id"], ["id"])
    op.create_unique_constraint("uq_users_driver_id", "users", ["driver_id"])
    op.add_column("vehicles", sa.Column("depot", sa.String(100), nullable=False, server_default="Ahmedabad Depot"))
    op.add_column("drivers", sa.Column("depot", sa.String(100), nullable=False, server_default="Ahmedabad Depot"))
    for name in ("source_latitude", "source_longitude", "destination_latitude", "destination_longitude"):
        op.add_column("trips", sa.Column(name, sa.Float(), nullable=True))

    preference_columns = [
        sa.Column("live_tracking_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("tracking_update_interval_seconds", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("tracking_stationary_interval_seconds", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("tracking_minimum_movement_meters", sa.Float(), nullable=False, server_default="20"),
        sa.Column("tracking_stale_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("tracking_offline_seconds", sa.Integer(), nullable=False, server_default="180"),
        sa.Column("tracking_raw_retention_days", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("driver_fleet_visibility", sa.String(40), nullable=False, server_default="OWN_VEHICLE_ONLY"),
        sa.Column("allow_driver_pause", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allow_driver_nearby_vehicles", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("map_provider", sa.String(40), nullable=False, server_default="openstreetmap"),
        sa.Column("directions_provider", sa.String(40), nullable=False, server_default="straight_line"),
        sa.Column("geofence_alerts_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    ]
    for column in preference_columns:
        op.add_column("preferences", column)

    op.create_table(
        "driver_tracking_sessions",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("driver_id", sa.String(40), sa.ForeignKey("drivers.id"), nullable=False),
        sa.Column("vehicle_id", sa.String(40), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("trip_id", sa.String(40), sa.ForeignKey("trips.id"), nullable=False),
        sa.Column("started_by_user_id", sa.String(40), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("consent_recorded_at", sa.DateTime(), nullable=False),
        sa.Column("consent_version", sa.String(20), nullable=False),
        sa.Column("start_reason", sa.String(100), nullable=False),
        sa.Column("end_reason", sa.String(100)),
        sa.Column("last_location_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    for name in ("driver_id", "vehicle_id", "trip_id", "status"):
        op.create_index(f"ix_driver_tracking_sessions_{name}", "driver_tracking_sessions", [name])
    for name in ("driver_id", "vehicle_id", "trip_id"):
        op.create_index(f"uq_active_tracking_{name}", "driver_tracking_sessions", [name], unique=True, postgresql_where=sa.text("status IN ('ACTIVE', 'PAUSED')"))

    op.create_table(
        "vehicle_location_points",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("tracking_session_id", sa.String(40), sa.ForeignKey("driver_tracking_sessions.id"), nullable=False),
        sa.Column("driver_id", sa.String(40), sa.ForeignKey("drivers.id"), nullable=False),
        sa.Column("vehicle_id", sa.String(40), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("trip_id", sa.String(40), sa.ForeignKey("trips.id"), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("accuracy_meters", sa.Float(), nullable=False),
        sa.Column("altitude", sa.Float()),
        sa.Column("altitude_accuracy", sa.Float()),
        sa.Column("heading_degrees", sa.Float()),
        sa.Column("speed_mps", sa.Float()),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("is_mock_location", sa.Boolean()),
        sa.Column("metadata", sa.JSON()),
        sa.CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_location_latitude"),
        sa.CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_location_longitude"),
        sa.CheckConstraint("accuracy_meters >= 0", name="ck_location_accuracy"),
        sa.UniqueConstraint("tracking_session_id", "source", "idempotency_key", name="uq_location_session_source_key"),
    )
    for name in ("tracking_session_id", "driver_id", "vehicle_id", "trip_id", "captured_at"):
        op.create_index(f"ix_vehicle_location_points_{name}", "vehicle_location_points", [name])
    op.create_index("ix_location_vehicle_captured", "vehicle_location_points", ["vehicle_id", sa.text("captured_at DESC")])
    op.create_index("ix_location_driver_captured", "vehicle_location_points", ["driver_id", sa.text("captured_at DESC")])
    op.create_index("ix_location_trip_captured", "vehicle_location_points", ["trip_id", sa.text("captured_at DESC")])
    op.create_index("ix_location_session_captured", "vehicle_location_points", ["tracking_session_id", "captured_at"])

    op.create_table(
        "latest_vehicle_locations",
        sa.Column("vehicle_id", sa.String(40), sa.ForeignKey("vehicles.id"), primary_key=True),
        sa.Column("trip_id", sa.String(40), sa.ForeignKey("trips.id"), nullable=False),
        sa.Column("driver_id", sa.String(40), sa.ForeignKey("drivers.id"), nullable=False),
        sa.Column("tracking_session_id", sa.String(40), sa.ForeignKey("driver_tracking_sessions.id"), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("speed_mps", sa.Float()),
        sa.Column("heading_degrees", sa.Float()),
        sa.Column("accuracy_meters", sa.Float(), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("freshness_status", sa.String(30), nullable=False),
    )
    for name in ("trip_id", "driver_id", "tracking_session_id"):
        op.create_index(f"ix_latest_vehicle_locations_{name}", "latest_vehicle_locations", [name])

    op.create_table(
        "geofences",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("depot_id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("center_latitude", sa.Float(), nullable=False),
        sa.Column("center_longitude", sa.Float(), nullable=False),
        sa.Column("radius_meters", sa.Float(), nullable=False),
        sa.Column("polygon_geojson", sa.JSON()),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(40), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("center_latitude >= -90 AND center_latitude <= 90", name="ck_geofence_latitude"),
        sa.CheckConstraint("center_longitude >= -180 AND center_longitude <= 180", name="ck_geofence_longitude"),
        sa.CheckConstraint("radius_meters > 0", name="ck_geofence_radius"),
    )
    op.create_index("ix_geofences_depot_id", "geofences", ["depot_id"])

    op.create_table(
        "geofence_events",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("geofence_id", sa.String(40), sa.ForeignKey("geofences.id"), nullable=False),
        sa.Column("vehicle_id", sa.String(40), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("driver_id", sa.String(40), sa.ForeignKey("drivers.id"), nullable=False),
        sa.Column("trip_id", sa.String(40), sa.ForeignKey("trips.id"), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("processed_at", sa.DateTime()),
        sa.Column("metadata", sa.JSON()),
    )
    for name in ("geofence_id", "vehicle_id", "driver_id", "trip_id"):
        op.create_index(f"ix_geofence_events_{name}", "geofence_events", [name])

    op.create_table(
        "tracking_alerts",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("vehicle_id", sa.String(40), sa.ForeignKey("vehicles.id")),
        sa.Column("driver_id", sa.String(40), sa.ForeignKey("drivers.id")),
        sa.Column("trip_id", sa.String(40), sa.ForeignKey("trips.id")),
        sa.Column("alert_type", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("message", sa.String(300), nullable=False),
        sa.Column("deduplication_key", sa.String(160), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime()),
    )
    for name in ("vehicle_id", "driver_id", "trip_id", "alert_type"):
        op.create_index(f"ix_tracking_alerts_{name}", "tracking_alerts", [name])


def downgrade() -> None:
    op.drop_table("tracking_alerts")
    op.drop_table("geofence_events")
    op.drop_table("geofences")
    op.drop_table("latest_vehicle_locations")
    op.drop_table("vehicle_location_points")
    op.drop_table("driver_tracking_sessions")
    for name in ("geofence_alerts_enabled", "directions_provider", "map_provider", "allow_driver_nearby_vehicles", "allow_driver_pause", "driver_fleet_visibility", "tracking_raw_retention_days", "tracking_offline_seconds", "tracking_stale_seconds", "tracking_minimum_movement_meters", "tracking_stationary_interval_seconds", "tracking_update_interval_seconds", "live_tracking_enabled"):
        op.drop_column("preferences", name)
    for name in ("destination_longitude", "destination_latitude", "source_longitude", "source_latitude"):
        op.drop_column("trips", name)
    op.drop_column("drivers", "depot")
    op.drop_column("vehicles", "depot")
    op.drop_constraint("uq_users_driver_id", "users", type_="unique")
    op.drop_constraint("fk_users_driver_id", "users", type_="foreignkey")
    op.drop_column("users", "region")
    op.drop_column("users", "driver_id")
