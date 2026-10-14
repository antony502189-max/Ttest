"""Track fulfillment independently of charging; snapshot advertising creatives."""
import sqlalchemy as sa
from alembic import op

revision = "0059_payment_fulfillment"
down_revision = "0058_advertising_waitlist"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payment_orders", sa.Column("fulfillment_status", sa.String(24), nullable=False, server_default="pending"))
    op.add_column("payment_orders", sa.Column("fulfillment_note", sa.Text()))
    op.add_column("payment_orders", sa.Column("advertisement_fingerprint", sa.String(64)))
    # Never re-grant historical paid TOP orders when a duplicate event arrives.
    op.execute("UPDATE payment_orders SET fulfillment_status = 'fulfilled' WHERE status = 'paid'")
    op.execute("""
        UPDATE payment_orders AS payment
        SET fulfillment_status = 'review_required',
            fulfillment_note = 'Historical paid advertising order has no paid campaign; reconcile before charging again.'
        WHERE payment.status = 'paid' AND payment.kind = 'advertisement'
          AND NOT EXISTS (
              SELECT 1 FROM commercial_advertisements AS ad
              WHERE ad.id = payment.target_id AND ad.owner_user_id = payment.owner_user_id
                AND ad.payment_status IN ('paid', 'refunded')
          )
    """)
    op.create_check_constraint("ck_payment_order_fulfillment", "payment_orders", "fulfillment_status IN ('pending','fulfilled','review_required')")


def downgrade() -> None:
    op.drop_constraint("ck_payment_order_fulfillment", "payment_orders", type_="check")
    for name in ("advertisement_fingerprint", "fulfillment_note", "fulfillment_status"):
        op.drop_column("payment_orders", name)
