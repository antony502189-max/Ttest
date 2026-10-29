"""Inert registered AI snapshots and fail-closed legacy discriminator."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0074_ai_saved_searches"
down_revision = "0073_ai_command_seed"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("saved_searches", sa.Column("matcher", sa.String(32), nullable=False, server_default="manual.v1"))
    op.alter_column("saved_searches", "rental_mode", nullable=True)
    op.create_unique_constraint("uq_saved_search_matcher", "saved_searches", ["id", "matcher"])
    op.create_check_constraint("ck_saved_search_matcher_boundary", "saved_searches",
        "(matcher = 'manual.v1' AND rental_mode IS NOT NULL) OR "
        "(matcher <> 'manual.v1' AND rental_mode IS NULL AND query = '' "
        "AND filters = '{}'::jsonb AND polygon = '[]'::jsonb AND alerts_enabled = false)")
    op.create_table("ai_saved_searches",
        sa.Column("saved_search_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("matcher", sa.String(32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("taxonomy_version", sa.String(32), nullable=False),
        sa.Column("criteria", postgresql.JSONB(), nullable=False),
        sa.Column("intent_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["saved_search_id", "matcher"], ["saved_searches.id", "saved_searches.matcher"],
                                ondelete="CASCADE", name="fk_ai_saved_search_matcher"),
        sa.CheckConstraint("matcher = 'ai.v1'", name="ck_ai_saved_matcher"),
        sa.CheckConstraint("revision > 0", name="ck_ai_saved_revision"),
        sa.CheckConstraint("schema_version = 'ai-search.v1' AND taxonomy_version = 'rental.v1'", name="ck_ai_saved_versions"),
        sa.CheckConstraint("intent_hash ~ '^[0-9a-f]{64}$'", name="ck_ai_saved_hash"),
        sa.CheckConstraint("jsonb_typeof(criteria) = 'object' AND octet_length(criteria::text) <= 65536",
                           name="ck_ai_saved_criteria"))


def downgrade():
    # Binary rollback preserves snapshots. Non-manual parents cannot enable
    # legacy alerts even if an older binary attempts to modify them.
    pass
