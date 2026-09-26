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
    op.add_column(
        "listings",
        sa.Column("video_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_listings_video_asset_id", "listings", ["video_asset_id"], unique=True)
    op.create_index("ix_media_assets_created_at", "media_assets", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_media_assets_created_at", table_name="media_assets")
    op.drop_index("ix_listings_video_asset_id", table_name="listings")
    op.drop_column("listings", "video_asset_id")
