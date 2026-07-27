"""add deduplicated daily listing view records"""

from alembic import op
import sqlalchemy as sa


revision = "0009_listing_views"
down_revision = "0008_listing_details"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "listing_views",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("listing_id", sa.Uuid(), sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("viewer_key", sa.String(64), nullable=False),
        sa.Column("view_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("listing_id", "viewer_key", "view_date", name="uq_listing_views_daily"),
    )
    op.create_index("ix_listing_views_listing_id", "listing_views", ["listing_id"])
    op.create_index("ix_listing_views_view_date", "listing_views", ["view_date"])


def downgrade():
    op.drop_table("listing_views")
