"""Minimal Stripe Checkout order ledger.

Revision ID: 0057_payment_orders
Revises: 0056_external_scope_checkpoint
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0057_payment_orders"
down_revision = "0056_external_scope_checkpoint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("stripe_session_id", sa.String(255), unique=True),
        sa.Column("checkout_url", sa.String(2048)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("kind IN ('advertisement','listing_top')", name="ck_payment_order_kind"),
        sa.CheckConstraint("status IN ('pending','paid','expired')", name="ck_payment_order_status"),
        sa.CheckConstraint("amount_cents > 0", name="ck_payment_order_amount"),
    )
    op.create_index("ix_payment_orders_owner_user_id", "payment_orders", ["owner_user_id"])
    op.create_index("ix_payment_orders_target_id", "payment_orders", ["target_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_orders_target_id", table_name="payment_orders")
    op.drop_index("ix_payment_orders_owner_user_id", table_name="payment_orders")
    op.drop_table("payment_orders")
