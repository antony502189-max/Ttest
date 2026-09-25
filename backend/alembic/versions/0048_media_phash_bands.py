"""index perceptual-hash bands for visual duplicate lookup

Revision ID: 0048_media_phash_bands
Revises: 0047_media_delivery_index
"""

import sqlalchemy as sa
from alembic import op

revision = "0048_media_phash_bands"
down_revision = "0047_media_delivery_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for band, offset in enumerate((1, 5, 9, 13), start=1):
        op.create_index(
            f"ix_media_assets_phash_band_{band}",
            "media_assets",
            [sa.text(f"substr(perceptual_hash, {offset}, 4)")],
            unique=False,
            postgresql_where=sa.text("perceptual_hash IS NOT NULL"),
        )


def downgrade() -> None:
    for band in range(1, 5):
        op.drop_index(f"ix_media_assets_phash_band_{band}", table_name="media_assets")
