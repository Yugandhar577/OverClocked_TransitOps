"""add driver profile photos

Revision ID: 0006_driver_profile_photos
Revises: 0005_add_fuel_receipts
Create Date: 2026-07-12
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_driver_profile_photos"
down_revision = "0005_add_fuel_receipts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("drivers", sa.Column("photo_url", sa.Text(), nullable=False, server_default=""))
    op.alter_column("drivers", "photo_url", server_default=None)


def downgrade() -> None:
    op.drop_column("drivers", "photo_url")
