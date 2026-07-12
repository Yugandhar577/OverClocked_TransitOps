"""Add configurable licence-expiry notification windows.

Revision ID: 0004_role_aware_dashboards
Revises: 0003_fleet_enrichment
Create Date: 2026-07-12 13:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_role_aware_dashboards"
down_revision = "0003_fleet_enrichment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("preferences", sa.Column("license_expiry_warning_days", sa.Integer(), nullable=False, server_default="30"))
    op.add_column("preferences", sa.Column("license_expiry_critical_days", sa.Integer(), nullable=False, server_default="7"))


def downgrade() -> None:
    op.drop_column("preferences", "license_expiry_critical_days")
    op.drop_column("preferences", "license_expiry_warning_days")
