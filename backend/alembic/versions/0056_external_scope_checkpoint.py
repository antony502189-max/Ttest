"""Add optional bounded provincial traversal state; existing scopes stay disabled."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0056_external_scope_checkpoint"
down_revision = "0055_external_removal_cursor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("external_import_scopes", sa.Column("discovery_checkpoint", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("external_import_scopes", "discovery_checkpoint")
