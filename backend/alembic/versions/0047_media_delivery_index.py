"""index reverse media lookups used by every public image request

Revision ID: 0047_media_delivery_index
Revises: 0046_owner_location_parity
"""

from alembic import op

revision = "0047_media_delivery_index"
down_revision = "0046_owner_location_parity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_listing_images_media_asset_id",
        "listing_images",
        ["media_asset_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_listing_images_media_asset_id", table_name="listing_images")
