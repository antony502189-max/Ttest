"""add recoverable mail delivery leases and retry scheduling

Revision ID: 0027_mail_delivery_leases
Revises: 0026_catalog_state_concurrency
"""

import sqlalchemy as sa
from alembic import op

revision = "0027_mail_delivery_leases"
down_revision = "0026_catalog_state_concurrency"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("mail_outbox", sa.Column("lease_token", sa.String(length=64), nullable=True))
    op.add_column("mail_outbox", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "mail_outbox",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_mail_outbox_lease_token", "mail_outbox", ["lease_token"], unique=False)
    op.create_index("ix_mail_outbox_lease_expires_at", "mail_outbox", ["lease_expires_at"], unique=False)
    op.create_index("ix_mail_outbox_next_attempt_at", "mail_outbox", ["next_attempt_at"], unique=False)
    op.create_index(
        "ix_mail_outbox_delivery_ready",
        "mail_outbox",
        ["next_attempt_at", "created_at"],
        unique=False,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade():
    op.drop_index("ix_mail_outbox_delivery_ready", table_name="mail_outbox")
    op.drop_index("ix_mail_outbox_next_attempt_at", table_name="mail_outbox")
    op.drop_index("ix_mail_outbox_lease_expires_at", table_name="mail_outbox")
    op.drop_index("ix_mail_outbox_lease_token", table_name="mail_outbox")
    op.drop_column("mail_outbox", "next_attempt_at")
    op.drop_column("mail_outbox", "lease_expires_at")
    op.drop_column("mail_outbox", "lease_token")
