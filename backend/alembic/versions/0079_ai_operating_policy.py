"""Independent proof age; no rewrite/backfill of live inputs or old migrations."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0079_ai_operating_policy"
down_revision = "0078_ai_live_validity"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("ai_proof_ages",
        sa.Column("canonical_listing_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("signature", sa.String(64), nullable=False),
        sa.Column("prepared_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("signature ~ '^[0-9a-f]{64}$'", name="ck_ai_proof_age_signature"))
    op.create_table("ai_erasure_bindings", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("journal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_ai_erasure_binding_singleton"))


def downgrade():
    raise RuntimeError("SCHEMA_DOWNGRADE_DISABLED: preserve AI erasure binding and use expand-only migrations")
