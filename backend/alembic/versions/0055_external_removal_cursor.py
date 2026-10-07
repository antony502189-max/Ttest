"""Index the finite active-source keyset sweep; no data changes."""

import sqlalchemy as sa

from alembic import op

revision = "0055_external_removal_cursor"
down_revision = "0054_recover_reexpired"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_external_removal_source_cursor",
        "external_listing_sources",
        ["source_name", "id"],
        postgresql_where=sa.text("current_status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("ix_external_removal_source_cursor", table_name="external_listing_sources")
