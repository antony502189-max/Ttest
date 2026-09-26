"""add one optional listing video

Revision ID: 0049_listing_video
Revises: 0048_media_phash_bands
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0049_listing_video"
down_revision = "0048_media_phash_bands"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE media_kind ADD VALUE IF NOT EXISTS 'listing_video'")
    op.add_column(
        "listings",
        sa.Column("video_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_listings_video_asset_id", "listings", ["video_asset_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_listings_video_asset_id", table_name="listings")
    op.drop_column("listings", "video_asset_id")
    # PostgreSQL enum values are intentionally left in place; removing an enum
    # value is not expand/rollback safe while an older application may still run.
