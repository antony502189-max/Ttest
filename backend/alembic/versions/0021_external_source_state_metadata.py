"""persist discovery and detail-state checks for external source records

Revision ID: 0021_source_state_metadata
Revises: 0020_external_lifecycle
"""

from alembic import op

revision = "0021_source_state_metadata"
down_revision = "0020_external_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE external_listing_sources ADD COLUMN IF NOT EXISTS last_discovered_at timestamptz")
    op.execute("ALTER TABLE external_listing_sources ADD COLUMN IF NOT EXISTS last_state_check_at timestamptz")
    op.execute("ALTER TABLE external_listing_sources ADD COLUMN IF NOT EXISTS last_state_check_result varchar(32)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_external_listing_sources_last_discovered_at "
        "ON external_listing_sources (last_discovered_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_external_listing_sources_last_state_check_at "
        "ON external_listing_sources (last_state_check_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_external_listing_sources_last_state_check_at")
    op.execute("DROP INDEX IF EXISTS ix_external_listing_sources_last_discovered_at")
    op.execute("ALTER TABLE external_listing_sources DROP COLUMN IF EXISTS last_state_check_result")
    op.execute("ALTER TABLE external_listing_sources DROP COLUMN IF EXISTS last_state_check_at")
    op.execute("ALTER TABLE external_listing_sources DROP COLUMN IF EXISTS last_discovered_at")
