"""Add structured room-first listing details.

Revision ID: 0034_room_first_listing_details
Revises: 0033_admin_moderation
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0034_room_first_listing_details"
down_revision: str | None = "0033_admin_moderation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "listing_room_details",
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("home_size_m2", sa.Integer(), nullable=True),
        sa.Column("bathroom_count", sa.Integer(), nullable=True),
        sa.Column("rental_unit", sa.String(length=16), nullable=True),
        sa.Column("bed_type", sa.String(length=16), nullable=True),
        sa.Column("bed_count", sa.Integer(), nullable=True),
        sa.Column("current_room_residents", sa.Integer(), nullable=True),
        sa.Column("toilet", sa.String(length=64), nullable=True),
        sa.Column("household_gender", sa.String(length=16), nullable=True),
        sa.Column("household_has_children", sa.Boolean(), nullable=True),
        sa.Column("heating_type", sa.String(length=16), nullable=True),
        sa.Column("accessible", sa.Boolean(), nullable=True),
        sa.Column("couples_allowed", sa.Boolean(), nullable=True),
        sa.Column("accepted_tenant_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.CheckConstraint("home_size_m2 IS NULL OR home_size_m2 BETWEEN 1 AND 10000", name="ck_room_details_home_size"),
        sa.CheckConstraint("bathroom_count IS NULL OR bathroom_count BETWEEN 0 AND 20", name="ck_room_details_bathroom_count"),
        sa.CheckConstraint("rental_unit IS NULL OR rental_unit IN ('room', 'bed')", name="ck_room_details_rental_unit"),
        sa.CheckConstraint("bed_type IS NULL OR bed_type IN ('single', 'double')", name="ck_room_details_bed_type"),
        sa.CheckConstraint("bed_count IS NULL OR bed_count BETWEEN 1 AND 10", name="ck_room_details_bed_count"),
        sa.CheckConstraint("current_room_residents IS NULL OR current_room_residents BETWEEN 0 AND 10", name="ck_room_details_current_room_residents"),
        sa.CheckConstraint("toilet IS NULL OR toilet IN ('Aseo privado', 'Aseo compartido')", name="ck_room_details_toilet"),
        sa.CheckConstraint("household_gender IS NULL OR household_gender IN ('men', 'women', 'mixed', 'unknown')", name="ck_room_details_household_gender"),
        sa.CheckConstraint("heating_type IS NULL OR heating_type IN ('individual', 'central', 'none', 'unknown')", name="ck_room_details_heating_type"),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("listing_id"),
    )


def downgrade() -> None:
    op.drop_table("listing_room_details")
