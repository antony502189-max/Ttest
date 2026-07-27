"""messages and reports"""

from alembic import op
import sqlalchemy as sa

revision = "0003_messages_reports"
down_revision = "0002_user_search_state"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "message_threads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("listing_id", sa.Uuid(), sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("host_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("listing_id", "tenant_id", name="uq_thread_listing_tenant"),
    )
    op.create_index("ix_message_threads_last_message_at", "message_threads", ["last_message_at"])
    op.create_index("ix_message_threads_listing_id", "message_threads", ["listing_id"])
    op.create_index("ix_message_threads_tenant_id", "message_threads", ["tenant_id"])
    op.create_index("ix_message_threads_host_id", "message_threads", ["host_id"])
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("thread_id", sa.Uuid(), sa.ForeignKey("message_threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_messages_thread_id", "messages", ["thread_id"])
    op.create_index("ix_messages_sender_id", "messages", ["sender_id"])
    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("public_reference", sa.String(24), nullable=False, unique=True),
        sa.Column("listing_id", sa.Uuid(), sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reporter_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reason", sa.String(120), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.Enum("open", "in_review", "resolved", "rejected", name="report_status"), nullable=False, server_default="open"),
        sa.Column("handled_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("handled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_reports_listing_id", "reports", ["listing_id"])
    op.create_index("ix_reports_reporter_id", "reports", ["reporter_id"])
    op.create_index("ix_reports_public_reference", "reports", ["public_reference"])
    op.create_index("ix_reports_status", "reports", ["status"])


def downgrade():
    op.drop_table("reports")
    op.drop_table("messages")
    op.drop_table("message_threads")
