"""Add the AI quota ledger without activating any AI endpoint or worker."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0067_ai_search_quota"
down_revision = "0066_complimentary_ads"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_usage_days",
        sa.Column("subject_kind", sa.String(5), primary_key=True),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("madrid_date", sa.Date(), primary_key=True),
        sa.Column(
            "quota_limit",
            sa.Integer(),
            sa.Computed("CASE subject_kind WHEN 'guest' THEN 3 ELSE 200 END", persisted=True),
            nullable=False,
        ),
        sa.Column("used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reserved", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("subject_kind IN ('guest', 'auth')", name="ck_ai_usage_subject_kind"),
        sa.CheckConstraint("used >= 0 AND reserved >= 0 AND used + reserved <= quota_limit", name="ck_ai_usage_bounds"),
    )
    op.create_table(
        "ai_search_requests",
        sa.Column("subject_kind", sa.String(5), primary_key=True),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("madrid_date", sa.Date(), nullable=False),
        sa.Column("channel", sa.String(5), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expected_session_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(9), nullable=False),
        sa.Column("fence", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recover_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("result_ref", postgresql.UUID(as_uuid=True)),
        sa.Column("result_count", sa.Integer()),
        sa.Column("failure_code", sa.String(40)),
        sa.ForeignKeyConstraint(
            ["subject_kind", "subject_id", "madrid_date"],
            ["ai_usage_days.subject_kind", "ai_usage_days.subject_id", "ai_usage_days.madrid_date"],
            name="fk_ai_request_day",
        ),
        sa.CheckConstraint("request_hash ~ '^[0-9a-f]{64}$'", name="ck_ai_request_hash"),
        sa.CheckConstraint("channel IN ('text', 'voice')", name="ck_ai_request_channel"),
        sa.CheckConstraint("expected_session_version >= 0 AND fence >= 0", name="ck_ai_request_versions"),
        sa.CheckConstraint("status IN ('reserved', 'running', 'succeeded', 'failed')", name="ck_ai_request_status"),
        sa.CheckConstraint("recover_after >= lease_until", name="ck_ai_request_recovery"),
        sa.CheckConstraint(
            "((status = 'succeeded') = (result_ref IS NOT NULL)) AND ((status = 'succeeded') = (result_count IS NOT NULL)) AND (result_count IS NULL OR result_count >= 0)",
            name="ck_ai_request_result",
        ),
        sa.CheckConstraint("(status = 'failed') = (failure_code IS NOT NULL)", name="ck_ai_request_failure"),
    )
    op.create_index(
        "ix_ai_request_recovery",
        "ai_search_requests",
        ["recover_after"],
        postgresql_where=sa.text("status IN ('reserved', 'running')"),
    )


def downgrade():
    # Expand-only rollback: old binaries ignore these tables. Never discard
    # reservations, terminal idempotency records or quota history on rollback.
    pass
