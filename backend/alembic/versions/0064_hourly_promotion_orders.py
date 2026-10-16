"""Record exact hour-based duration for future TOP and homepage orders.

Revision ID: 0064_hourly_promotion_orders
Revises: 0063_financial_inbox_receipts

Existing orders keep NULL and retain their original day/month fulfillment rules.
"""

from alembic import op
import sqlalchemy as sa

revision = "0064_hourly_promotion_orders"
down_revision = "0063_financial_inbox_receipts"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("payment_orders", sa.Column("duration_hours", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_payment_order_hourly_promotion",
        "payment_orders",
        "duration_hours IS NULL OR (kind IN ('listing_top','homepage_hero') AND duration_hours IN (12,24,72) AND duration_months IS NULL)",
    )


def downgrade():
    # Paid and pending hour-based entitlements must survive application rollback.
    from sqlalchemy import text

    connection = op.get_bind()
    if connection.execute(text("SELECT 1 FROM payment_orders WHERE duration_hours IS NOT NULL LIMIT 1")).first():
        raise RuntimeError("Cannot discard paid/pending hourly promotion history")
    op.drop_constraint("ck_payment_order_hourly_promotion", "payment_orders", type_="check")
    op.drop_column("payment_orders", "duration_hours")
