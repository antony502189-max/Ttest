"""Add inert current-query verification cache; no population or activation."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0071_ai_query_proofs"
down_revision = "0070_ai_fact_pipeline"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("ai_query_proofs",
        sa.Column("canonical_listing_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("signature", sa.String(64), nullable=False),
        sa.Column("vocabulary_hash", sa.String(64), nullable=False),
        sa.Column("resolver_version", sa.String(64), nullable=False),
        sa.Column("feature_revision", sa.Integer(), nullable=False),
        sa.CheckConstraint("signature ~ '^[0-9a-f]{64}$' AND vocabulary_hash ~ '^[0-9a-f]{64}$'", name="ck_ai_query_proof_hashes"),
        sa.CheckConstraint("feature_revision > 0", name="ck_ai_query_proof_revision"),
        sa.CheckConstraint("resolver_version ~ '^[a-zA-Z0-9][a-zA-Z0-9._-]*$'", name="ck_ai_query_proof_resolver"))


def downgrade():
    # Binary rollback preserves additive history/cache; old binaries ignore it.
    pass
