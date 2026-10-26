"""Add structured AI sessions/results. Does not enable any AI endpoint."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0068_ai_search_sessions"
down_revision = "0067_ai_search_quota"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_search_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("subject_kind", sa.String(5), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("taxonomy_version", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("criteria", postgresql.JSONB(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("subject_kind IN ('guest', 'auth')", name="ck_ai_session_subject"),
        sa.CheckConstraint("version >= 0", name="ck_ai_session_version"),
        sa.CheckConstraint(
            "jsonb_typeof(criteria) = 'object' AND octet_length(criteria::text) <= 65536", name="ck_ai_session_criteria"
        ),
    )
    op.create_index("ix_ai_session_owner", "ai_search_sessions", ["subject_kind", "subject_id"])
    op.create_table(
        "ai_search_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("subject_kind", sa.String(5), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_search_sessions.id"), nullable=False),
        sa.Column("session_version", sa.Integer(), nullable=False),
        sa.Column("intent", postgresql.JSONB(), nullable=False),
        sa.Column("intent_hash", sa.String(64), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["subject_kind", "subject_id", "idempotency_key"],
            ["ai_search_requests.subject_kind", "ai_search_requests.subject_id", "ai_search_requests.idempotency_key"],
            name="fk_ai_result_operation",
        ),
        sa.UniqueConstraint("subject_kind", "subject_id", "idempotency_key", name="uq_ai_result_operation"),
        sa.CheckConstraint("session_version > 0 AND result_count >= 0", name="ck_ai_result_counts"),
        sa.CheckConstraint(
            "jsonb_typeof(intent) = 'object' AND octet_length(intent::text) <= 65536", name="ck_ai_result_intent"
        ),
        sa.CheckConstraint("intent_hash ~ '^[0-9a-f]{64}$'", name="ck_ai_result_hash"),
    )


def downgrade():
    # Expand-only rollback keeps quota/result/session history for old binaries.
    pass
