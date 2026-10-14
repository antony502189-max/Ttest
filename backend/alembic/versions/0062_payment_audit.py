"""Durable Checkout attempts, financial inbox and purchased service history."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0062_payment_audit"
down_revision = "0061_monthly_top"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_payment_order_fulfillment", "payment_orders", type_="check")
    op.create_check_constraint("ck_payment_order_fulfillment", "payment_orders", "fulfillment_status IN ('pending','fulfilled','review_required','revoked')")
    op.drop_constraint("ck_payment_order_status", "payment_orders", type_="check")
    op.create_check_constraint("ck_payment_order_status", "payment_orders", "status IN ('creating','pending','paid','expired','failed')")
    for name, kind in [("checkout_name",sa.String(240)),("return_path",sa.String(512)),
                       ("stripe_payment_intent_id",sa.String(255)),("stripe_charge_id",sa.String(255)),
                       ("dispute_status",sa.String(48)),("refund_id",sa.String(255)),("paused_ad_status",sa.String(24)),
                       ("resolution_reason",sa.Text()),("resolution_actor_id",postgresql.UUID(as_uuid=True)),
                       ("refund_requested_at",sa.DateTime(timezone=True)),("resolved_at",sa.DateTime(timezone=True)),
                       ("service_starts_at",sa.DateTime(timezone=True)),("service_ends_at",sa.DateTime(timezone=True))]:
        op.add_column("payment_orders",sa.Column(name,kind,nullable=True))
    op.add_column("payment_orders",sa.Column("financial_status",sa.String(24),server_default="normal",nullable=False))
    op.add_column("payment_orders",sa.Column("refunded_amount_cents",sa.Integer(),server_default="0",nullable=False))
    op.add_column("payment_orders",sa.Column("refund_attempt",sa.Integer(),server_default="0",nullable=False))
    op.create_unique_constraint("uq_payment_orders_stripe_payment_intent_id","payment_orders",["stripe_payment_intent_id"])
    op.create_index("ix_payment_orders_stripe_charge_id","payment_orders",["stripe_charge_id"])
    op.create_foreign_key("fk_payment_resolution_actor","payment_orders","users",["resolution_actor_id"],["id"],ondelete="SET NULL")
    op.create_table("payment_events",sa.Column("id",sa.String(255),primary_key=True),
                    sa.Column("payment_intent_id",sa.String(255),nullable=False),sa.Column("event_type",sa.String(80),nullable=False),
                    sa.Column("snapshot",postgresql.JSONB(),nullable=False),sa.Column("received_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index("ix_payment_events_payment_intent_id","payment_events",["payment_intent_id"])
    op.add_column("commercial_advertisements",sa.Column("current_payment_order_id",postgresql.UUID(as_uuid=True),nullable=True))
    op.add_column("homepage_hero_promotions",sa.Column("payment_order_id",postgresql.UUID(as_uuid=True),nullable=True))
    op.add_column("listing_promotions",sa.Column("payment_managed",sa.Boolean(),server_default=sa.false(),nullable=False))
    op.add_column("listing_promotions",sa.Column("baseline_starts_at",sa.DateTime(timezone=True),nullable=True))
    op.add_column("listing_promotions",sa.Column("baseline_ends_at",sa.DateTime(timezone=True),nullable=True))
    op.execute("UPDATE commercial_advertisements a SET current_payment_order_id = (SELECT p.id FROM payment_orders p WHERE p.target_id=a.id AND p.kind='advertisement' AND p.status='paid' AND p.fulfillment_status='fulfilled' ORDER BY p.paid_at DESC LIMIT 1)")
    op.execute("UPDATE homepage_hero_promotions h SET payment_order_id = (SELECT p.id FROM payment_orders p WHERE p.target_id=h.listing_id AND p.kind='homepage_hero' AND p.status='paid' AND p.fulfillment_status='fulfilled' AND p.paid_at>=h.starts_at ORDER BY p.paid_at DESC LIMIT 1)")
    op.execute("UPDATE payment_orders p SET service_starts_at=h.starts_at,service_ends_at=h.ends_at FROM homepage_hero_promotions h WHERE h.payment_order_id=p.id")
    op.execute("UPDATE payment_orders p SET service_starts_at=a.starts_at,service_ends_at=a.ends_at FROM commercial_advertisements a WHERE a.current_payment_order_id=p.id")


def downgrade():
    op.drop_column("listing_promotions","baseline_starts_at")
    op.drop_column("listing_promotions","baseline_ends_at")
    op.drop_column("listing_promotions","payment_managed")
    op.drop_column("homepage_hero_promotions","payment_order_id")
    op.drop_column("commercial_advertisements","current_payment_order_id")
    op.drop_table("payment_events")
    op.drop_constraint("fk_payment_resolution_actor","payment_orders",type_="foreignkey")
    op.drop_index("ix_payment_orders_stripe_charge_id",table_name="payment_orders")
    op.drop_constraint("uq_payment_orders_stripe_payment_intent_id","payment_orders",type_="unique")
    for name in ["checkout_name","return_path","stripe_payment_intent_id","stripe_charge_id","dispute_status","refund_id","resolution_reason","resolution_actor_id","refund_requested_at","resolved_at","service_starts_at","service_ends_at","financial_status","refunded_amount_cents","paused_ad_status","refund_attempt"]:
        op.drop_column("payment_orders",name)
    op.drop_constraint("ck_payment_order_status","payment_orders",type_="check")
    op.create_check_constraint("ck_payment_order_status","payment_orders","status IN ('pending','paid','expired')")
    op.drop_constraint("ck_payment_order_fulfillment", "payment_orders", type_="check")
    op.create_check_constraint("ck_payment_order_fulfillment", "payment_orders", "fulfillment_status IN ('pending','fulfilled','review_required')")
