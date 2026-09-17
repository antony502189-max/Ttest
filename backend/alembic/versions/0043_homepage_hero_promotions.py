"""add singleton homepage hero promotion

Revision ID: 0043_homepage_hero_promotions
Revises: 0042_timed_listing_promotions
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0043_homepage_hero_promotions"
down_revision = "0042_timed_listing_promotions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "homepage_hero_promotions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("configured_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("configured_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_homepage_hero_promotions_singleton"),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["configured_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_homepage_hero_promotions_listing_id", "homepage_hero_promotions", ["listing_id"], unique=False)
    op.create_index("ix_homepage_hero_promotions_starts_at", "homepage_hero_promotions", ["starts_at"], unique=False)
    op.create_index("ix_homepage_hero_promotions_ends_at", "homepage_hero_promotions", ["ends_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_homepage_hero_promotions_ends_at", table_name="homepage_hero_promotions")
    op.drop_index("ix_homepage_hero_promotions_starts_at", table_name="homepage_hero_promotions")
    op.drop_index("ix_homepage_hero_promotions_listing_id", table_name="homepage_hero_promotions")
    op.drop_table("homepage_hero_promotions")
