"""Add vehicle compliance, odometer history, and enhanced maintenance fields.

Revision ID: 0002_fleet_enrichment
Revises: 0001_initial_schema
Create Date: 2026-07-12 00:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_fleet_enrichment"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, column in (
        ("brand", sa.Column("brand", sa.String(60), nullable=False, server_default="")),
        ("model", sa.Column("model", sa.String(60), nullable=False, server_default="")),
        ("vin", sa.Column("vin", sa.String(64), nullable=False, server_default="")),
        ("fuel_type", sa.Column("fuel_type", sa.String(20), nullable=False, server_default="Diesel")),
        ("manufacture_year", sa.Column("manufacture_year", sa.Integer(), nullable=True)),
        ("color", sa.Column("color", sa.String(40), nullable=False, server_default="")),
        ("photo_url", sa.Column("photo_url", sa.Text(), nullable=False, server_default="")),
    ):
        op.add_column("vehicles", column)

    for name, column in (
        ("vendor", sa.Column("vendor", sa.String(80), nullable=False, server_default="")),
        ("odometer_km", sa.Column("odometer_km", sa.Float(), nullable=True)),
        ("invoice_reference", sa.Column("invoice_reference", sa.String(80), nullable=False, server_default="")),
        ("priority", sa.Column("priority", sa.String(20), nullable=False, server_default="Normal")),
        ("due_date", sa.Column("due_date", sa.Date(), nullable=True)),
    ):
        op.add_column("maintenance", column)
    op.create_index("ix_maintenance_priority", "maintenance", ["priority"])

    op.create_table(
        "vehicle_documents",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("vehicle_id", sa.String(40), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("reference_number", sa.String(80), nullable=False, server_default=""),
        sa.Column("provider", sa.String(100), nullable=False, server_default=""),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="Active"),
        sa.CheckConstraint("cost >= 0", name="ck_vehicle_documents_cost_nonnegative"),
    )
    op.create_index("ix_vehicle_documents_vehicle_id", "vehicle_documents", ["vehicle_id"])
    op.create_index("ix_vehicle_documents_document_type", "vehicle_documents", ["document_type"])
    op.create_index("ix_vehicle_documents_expiry_date", "vehicle_documents", ["expiry_date"])
    op.create_index("ix_vehicle_documents_status", "vehicle_documents", ["status"])

    op.create_table(
        "odometer_logs",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("vehicle_id", sa.String(40), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("value_km", sa.Float(), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("driver_id", sa.String(40), sa.ForeignKey("drivers.id")),
        sa.CheckConstraint("value_km >= 0", name="ck_odometer_logs_value_nonnegative"),
    )
    op.create_index("ix_odometer_logs_vehicle_id", "odometer_logs", ["vehicle_id"])
    op.create_index("ix_odometer_logs_date", "odometer_logs", ["date"])
    op.create_index("ix_odometer_logs_driver_id", "odometer_logs", ["driver_id"])


def downgrade() -> None:
    op.drop_table("odometer_logs")
    op.drop_table("vehicle_documents")
    op.drop_index("ix_maintenance_priority", table_name="maintenance")
    for name in ("due_date", "priority", "invoice_reference", "odometer_km", "vendor"):
        op.drop_column("maintenance", name)
    for name in ("photo_url", "color", "manufacture_year", "fuel_type", "vin", "model", "brand"):
        op.drop_column("vehicles", name)
