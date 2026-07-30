"""separate unknown detail-state fallback from missing counters

Revision ID: 0022_unknown_state_counter
Revises: 0021_source_state_metadata
"""

from alembic import op

revision = "0022_unknown_state_counter"
down_revision = "0021_source_state_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE external_listing_sources ADD COLUMN IF NOT EXISTS "
        "consecutive_unknown_state_runs integer NOT NULL DEFAULT 0"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE external_listing_sources DROP COLUMN IF EXISTS consecutive_unknown_state_runs")
