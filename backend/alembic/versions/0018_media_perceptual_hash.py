"""store perceptual hashes for external image deduplication

Revision ID: 0018_media_perceptual_hash
Revises: 0017_nullable_external_unknowns
"""

from alembic import op

revision = "0018_media_perceptual_hash"
down_revision = "0017_nullable_external_unknowns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS perceptual_hash varchar(16)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_media_assets_perceptual_hash ON media_assets (perceptual_hash)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_media_assets_perceptual_hash")
    op.execute("ALTER TABLE media_assets DROP COLUMN IF EXISTS perceptual_hash")
