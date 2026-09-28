"""Add disabled geographic import scope scheduling.

Revision ID: 0051_external_import_scopes
Revises: 0050_spain_search_indexes
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0051_external_import_scopes"
down_revision = "0050_spain_search_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("external_listing_sources", sa.Column(
        "scope_key", sa.String(120), nullable=False, server_default="santa_cruz",
    ))
    op.add_column("external_import_runs", sa.Column(
        "scope_key", sa.String(120), nullable=False, server_default="santa_cruz",
    ))
    op.create_index("ix_external_listing_sources_scope_key", "external_listing_sources", ["scope_key"])
    op.create_index("ix_external_import_runs_scope_key", "external_import_runs", ["scope_key"])
    op.create_table(
        "external_import_scopes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_name", sa.String(64), nullable=False),
        sa.Column("scope_key", sa.String(120), nullable=False),
        sa.Column("discovery_urls", postgresql.JSONB(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("interval_seconds", sa.Integer(), nullable=False, server_default="86400"),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("last_result", sa.String(32)),
        sa.UniqueConstraint("source_name", "scope_key", name="uq_external_import_scope"),
    )
    op.create_index("ix_external_import_scopes_due", "external_import_scopes", ["enabled", "next_run_at"])


def downgrade() -> None:
    op.drop_index("ix_external_import_scopes_due", table_name="external_import_scopes")
    op.drop_table("external_import_scopes")
    op.drop_index("ix_external_import_runs_scope_key", table_name="external_import_runs")
    op.drop_index("ix_external_listing_sources_scope_key", table_name="external_listing_sources")
    op.drop_column("external_import_runs", "scope_key")
    op.drop_column("external_listing_sources", "scope_key")
