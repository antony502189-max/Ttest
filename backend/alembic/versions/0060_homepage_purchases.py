"""Paid homepage placement and variable banner duration.

Revision ID: 0060_homepage_purchases
Revises: 0059_payment_fulfillment
"""
from alembic import op
import sqlalchemy as sa

revision = "0060_homepage_purchases"
down_revision = "0059_payment_fulfillment"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("commercial_advertisements", sa.Column("duration_days", sa.Integer(), nullable=True))
    op.drop_constraint("ck_payment_order_kind", "payment_orders", type_="check")
    op.create_check_constraint("ck_payment_order_kind", "payment_orders", "kind IN ('advertisement','listing_top','homepage_hero')")


def downgrade():
    # Refuse to discard paid service history when reverting the application.
    op.create_check_constraint("ck_payment_order_kind_old", "payment_orders", "kind IN ('advertisement','listing_top')")
    op.drop_constraint("ck_payment_order_kind", "payment_orders", type_="check")
    op.drop_constraint("ck_payment_order_kind_old", "payment_orders", type_="check")
    op.create_check_constraint("ck_payment_order_kind", "payment_orders", "kind IN ('advertisement','listing_top')")
    op.drop_column("commercial_advertisements", "duration_days")
