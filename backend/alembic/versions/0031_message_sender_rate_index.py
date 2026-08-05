"""Index per-account message rate scans.

Revision ID: 0031_message_sender_rate_index
Revises: 0030_storage_deletions
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0031_message_sender_rate_index"
down_revision: str | None = "0030_storage_deletions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_messages_sender_created_at",
        "messages",
        ["sender_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_messages_sender_created_at", table_name="messages")
