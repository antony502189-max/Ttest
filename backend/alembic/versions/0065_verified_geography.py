"""Expand geography without guessing private owner addresses or rewriting history."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0065_verified_geography"
down_revision = "0064_hourly_promotion_orders"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("verified_address", postgresql.JSONB(), nullable=True))
    op.add_column("users", sa.Column("municipality_code", sa.String(5), nullable=True))
    op.add_column("users", sa.Column("address_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_municipality_code", "users", ["municipality_code"])
    op.add_column("listings", sa.Column("province_code", sa.String(2), nullable=True))
    op.add_column("listings", sa.Column("address_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_listings_province_code", "listings", ["province_code"])
    op.add_column("saved_searches", sa.Column("province_code", sa.String(2), nullable=True))
    op.add_column("payment_orders", sa.Column("top_municipality_code", sa.String(5), nullable=True))
    op.create_index("ix_payment_orders_top_municipality_code", "payment_orders", ["top_municipality_code"])
    op.add_column("listing_promotions", sa.Column("top_municipality_code", sa.String(5), nullable=True))
    op.create_index("ix_listing_promotions_top_municipality_code", "listing_promotions", ["top_municipality_code"])


def downgrade():
    # Rollback binaries tolerate nullable expansion fields. Keep verified data.
    pass
