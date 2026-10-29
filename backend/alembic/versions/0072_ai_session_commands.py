"""Durable owned create/reset receipts. No AI activation or text storage."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "0072_ai_session_commands"
down_revision = "0071_ai_query_proofs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("ai_session_commands",
        sa.Column("subject_kind", sa.String(5), primary_key=True),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("action", sa.String(6), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_search_sessions.id")),
        sa.Column("expected_version", sa.Integer()),
        sa.Column("result_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_search_sessions.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("subject_kind IN ('guest', 'auth')", name="ck_ai_command_subject"),
        sa.CheckConstraint("(action = 'create' AND source_id IS NULL AND expected_version IS NULL) OR "
                           "(action = 'reset' AND source_id IS NOT NULL AND expected_version IS NOT NULL AND expected_version >= 0)",
                           name="ck_ai_command_action"))


def downgrade():
    # Expand-only: keep recovery receipts and session references for old binaries.
    pass
