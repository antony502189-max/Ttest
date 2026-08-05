"""Index bounded retention scans.

Revision ID: 0028_data_retention_indexes
Revises: 0027_mail_delivery_leases
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0028_data_retention_indexes"
down_revision: str | None = "0027_mail_delivery_leases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_auth_sessions_expires_at",
        "auth_sessions",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_mail_outbox_status_created_at",
        "mail_outbox",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_mail_outbox_status_created_at", table_name="mail_outbox")
    op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions")
