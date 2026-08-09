"""Add database-backed admin access and moderation records.

Revision ID: 0033_admin_moderation
Revises: 0032_media_reference_guard
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0033_admin_moderation"
down_revision: str | None = "0032_media_reference_guard"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INITIAL_ADMIN_EMAILS = ("tf.shuler@gmail.com", "antony502189@gmail.com")


def upgrade() -> None:
    op.create_table(
        "admin_access",
        sa.Column("email", sa.String(length=320), primary_key=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_admin_access_active", "admin_access", ["active"])
    op.create_index("ix_admin_access_created_by", "admin_access", ["created_by"])

    op.create_table(
        "user_restrictions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("restriction_type", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expiry_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "restriction_type IN ('full', 'publish', 'view_listings')",
            name="ck_user_restrictions_type",
        ),
        sa.CheckConstraint("ends_at > starts_at", name="ck_user_restrictions_dates"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["revoked_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_user_restrictions_user_id", "user_restrictions", ["user_id"])
    op.create_index("ix_user_restrictions_type", "user_restrictions", ["restriction_type"])
    op.create_index("ix_user_restrictions_starts_at", "user_restrictions", ["starts_at"])
    op.create_index("ix_user_restrictions_ends_at", "user_restrictions", ["ends_at"])
    op.create_index("ix_user_restrictions_created_by", "user_restrictions", ["created_by"])
    op.create_index("ix_user_restrictions_revoked_at", "user_restrictions", ["revoked_at"])
    op.create_index("ix_user_restrictions_expiry_notified_at", "user_restrictions", ["expiry_notified_at"])

    op.create_table(
        "listing_restrictions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expiry_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("ends_at > starts_at", name="ck_listing_restrictions_dates"),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["revoked_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_listing_restrictions_listing_id", "listing_restrictions", ["listing_id"])
    op.create_index("ix_listing_restrictions_starts_at", "listing_restrictions", ["starts_at"])
    op.create_index("ix_listing_restrictions_ends_at", "listing_restrictions", ["ends_at"])
    op.create_index("ix_listing_restrictions_created_by", "listing_restrictions", ["created_by"])
    op.create_index("ix_listing_restrictions_revoked_at", "listing_restrictions", ["revoked_at"])
    op.create_index("ix_listing_restrictions_expiry_notified_at", "listing_restrictions", ["expiry_notified_at"])

    op.create_table(
        "admin_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_admin_notes_user_id", "admin_notes", ["user_id"])
    op.create_index("ix_admin_notes_created_by", "admin_notes", ["created_by"])
    op.create_index("ix_admin_notes_created_at", "admin_notes", ["created_at"])

    op.create_table(
        "moderation_notices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=48), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_moderation_notices_user_id", "moderation_notices", ["user_id"])
    op.create_index("ix_moderation_notices_kind", "moderation_notices", ["kind"])
    op.create_index("ix_moderation_notices_created_at", "moderation_notices", ["created_at"])
    op.create_index("ix_moderation_notices_read_at", "moderation_notices", ["read_at"])

    admin_access = sa.table(
        "admin_access",
        sa.column("email", sa.String(length=320)),
        sa.column("active", sa.Boolean()),
    )
    op.bulk_insert(admin_access, [{"email": email, "active": True} for email in INITIAL_ADMIN_EMAILS])


def downgrade() -> None:
    op.drop_table("moderation_notices")
    op.drop_table("admin_notes")
    op.drop_table("listing_restrictions")
    op.drop_table("user_restrictions")
    op.drop_table("admin_access")
