"""add fuel receipt data

Revision ID: 0004_add_fuel_receipts
Revises: 0003_fleet_enrichment
Create Date: 2026-07-12
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_add_fuel_receipts"
down_revision = "0003_fleet_enrichment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fuel_logs", sa.Column("price_per_liter", sa.Float(), nullable=True))
    op.add_column("fuel_logs", sa.Column("receipt_image", sa.String(length=512), nullable=True))
    op.execute("UPDATE fuel_logs SET price_per_liter = cost / liters WHERE price_per_liter IS NULL")
    op.alter_column("fuel_logs", "price_per_liter", nullable=False)
    op.create_check_constraint("ck_fuel_price_per_liter_positive", "fuel_logs", "price_per_liter > 0")


def downgrade() -> None:
    op.drop_constraint("ck_fuel_price_per_liter_positive", "fuel_logs", type_="check")
    op.drop_column("fuel_logs", "receipt_image")
    op.drop_column("fuel_logs", "price_per_liter")
