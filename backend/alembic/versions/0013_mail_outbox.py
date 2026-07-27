"""add transactional mail outbox"""

from alembic import op
import sqlalchemy as sa

revision = "0013_mail_outbox"
down_revision = "0012_email_verification_tokens"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mail_outbox",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("recipient", sa.String(320), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_mail_outbox_kind", "mail_outbox", ["kind"])
    op.create_index("ix_mail_outbox_recipient", "mail_outbox", ["recipient"])
    op.create_index("ix_mail_outbox_status", "mail_outbox", ["status"])


def downgrade():
    op.drop_table("mail_outbox")
