"""add the full listing-domain fields used by the client"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0008_listing_details"
down_revision = "0007_listing_private_location"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("listings", sa.Column("weekly_price", sa.Integer()))
    op.add_column("listings", sa.Column("room_type", sa.String(64), nullable=False, server_default="Habitación individual"))
    op.add_column("listings", sa.Column("available_from", sa.Date()))
    op.add_column("listings", sa.Column("available_until", sa.Date()))
    op.add_column("listings", sa.Column("minimum_stay_months", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("listings", sa.Column("minimum_nights", sa.Integer()))
    op.add_column("listings", sa.Column("deposit_amount", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("listings", sa.Column("bills_included", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("listings", sa.Column("bathroom", sa.String(64), nullable=False, server_default="Baño compartido"))
    op.add_column("listings", sa.Column("kitchen", sa.String(64), nullable=False, server_default="Cocina compartida"))
    op.add_column("listings", sa.Column("furnished", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("listings", sa.Column("room_size_m2", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("listings", sa.Column("bedroom_count", sa.Integer()))
    op.add_column("listings", sa.Column("current_residents", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("listings", sa.Column("room_capacity", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("listings", sa.Column("shower", sa.String(64), nullable=False, server_default="Ducha compartida"))
    op.add_column("listings", sa.Column("tenant_requirement", sa.String(32), nullable=False, server_default="any"))
    op.add_column("listings", sa.Column("smoking_allowed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("listings", sa.Column("pets_allowed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("listings", sa.Column("children_allowed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("listings", sa.Column("empadronamiento_allowed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("listings", sa.Column("restrictions", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column("listings", sa.Column("amenities", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column("listings", sa.Column("home_description", sa.Text(), nullable=False, server_default=""))
    op.add_column("listings", sa.Column("advertiser_type", sa.String(32), nullable=False, server_default="Particular"))
    op.add_column("listings", sa.Column("source", sa.String(120)))
    op.add_column("listings", sa.Column("published_at", sa.DateTime(timezone=True)))
    op.add_column("listings", sa.Column("expires_at", sa.DateTime(timezone=True)))
    op.add_column("listings", sa.Column("views", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("listings", sa.Column("closed_reason", sa.String(32)))
    op.add_column("listings", sa.Column("deleted_at", sa.DateTime(timezone=True)))
    op.create_index("ix_listings_published_at", "listings", ["published_at"])
    op.create_index("ix_listings_expires_at", "listings", ["expires_at"])
    op.create_index("ix_listings_deleted_at", "listings", ["deleted_at"])
    op.create_check_constraint("ck_listings_weekly_price_nonnegative", "listings", "weekly_price IS NULL OR weekly_price >= 0")
    op.create_check_constraint("ck_listings_minimum_stay_nonnegative", "listings", "minimum_stay_months >= 0")
    op.create_check_constraint("ck_listings_minimum_nights_nonnegative", "listings", "minimum_nights IS NULL OR minimum_nights >= 0")
    op.create_check_constraint("ck_listings_deposit_nonnegative", "listings", "deposit_amount >= 0")
    op.create_check_constraint("ck_listings_room_size_range", "listings", "room_size_m2 BETWEEN 1 AND 10000")
    op.create_check_constraint("ck_listings_bedroom_count_range", "listings", "bedroom_count IS NULL OR bedroom_count BETWEEN 1 AND 99")
    op.create_check_constraint("ck_listings_residents_nonnegative", "listings", "current_residents >= 0")
    op.create_check_constraint("ck_listings_room_capacity", "listings", "room_capacity IN (1, 2)")
    op.create_check_constraint("ck_listings_views_nonnegative", "listings", "views >= 0")
    op.create_check_constraint("ck_listings_available_dates", "listings", "available_until IS NULL OR available_from IS NULL OR available_until >= available_from")


def downgrade():
    for name in (
        "ck_listings_available_dates", "ck_listings_views_nonnegative", "ck_listings_room_capacity",
        "ck_listings_residents_nonnegative", "ck_listings_bedroom_count_range", "ck_listings_room_size_range",
        "ck_listings_deposit_nonnegative", "ck_listings_minimum_nights_nonnegative",
        "ck_listings_minimum_stay_nonnegative", "ck_listings_weekly_price_nonnegative",
    ):
        op.drop_constraint(name, "listings", type_="check")
    for name in ("ix_listings_deleted_at", "ix_listings_expires_at", "ix_listings_published_at"):
        op.drop_index(name, table_name="listings")
    for name in (
        "deleted_at", "closed_reason", "views", "expires_at", "published_at", "source", "advertiser_type",
        "home_description", "amenities", "restrictions", "empadronamiento_allowed", "children_allowed",
        "pets_allowed", "smoking_allowed", "tenant_requirement", "shower", "room_capacity", "current_residents",
        "bedroom_count", "room_size_m2", "furnished", "kitchen", "bathroom", "bills_included", "deposit_amount",
        "minimum_nights", "minimum_stay_months", "available_until", "available_from", "room_type", "weekly_price",
    ):
        op.drop_column("listings", name)
