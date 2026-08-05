"""Add durable object-storage deletion jobs.

Revision ID: 0030_storage_deletions
Revises: 0029_import_run_retention
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0030_storage_deletions"
down_revision: str | None = "0029_import_run_retention"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "storage_deletion_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("lease_token", sa.String(length=64), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_storage_deletion_jobs_storage_key"),
    )
    op.create_index(
        "ix_storage_deletion_jobs_next_attempt_at",
        "storage_deletion_jobs",
        ["next_attempt_at"],
        unique=False,
    )
    op.create_index(
        "ix_storage_deletion_jobs_lease_expires_at",
        "storage_deletion_jobs",
        ["lease_expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_storage_deletion_jobs_lease_token",
        "storage_deletion_jobs",
        ["lease_token"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_storage_deletion_jobs_lease_token", table_name="storage_deletion_jobs")
    op.drop_index("ix_storage_deletion_jobs_lease_expires_at", table_name="storage_deletion_jobs")
    op.drop_index("ix_storage_deletion_jobs_next_attempt_at", table_name="storage_deletion_jobs")
    op.drop_table("storage_deletion_jobs")
