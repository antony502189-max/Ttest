"""Dedicated first-party commercial advertisements.

Revision ID: 0052_commercial_advertisements
Revises: 0051_external_import_scopes
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0052_commercial_advertisements"
down_revision = "0051_external_import_scopes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ADD VALUE needs its own committed transaction before the value
    # can be used by later DML on PostgreSQL.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE media_kind ADD VALUE IF NOT EXISTS 'advertisement_image'")
    op.create_table(
        "commercial_advertisements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("image_asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("media_assets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(90), nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("destination_type", sa.String(16), nullable=False),
        sa.Column("destination", sa.String(2048), nullable=False),
        sa.Column("placement", sa.String(40), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("payment_status", sa.String(16), nullable=False),
        sa.Column("package_id", sa.String(40), nullable=False),
        sa.Column("admin_priority", sa.Integer(), nullable=False),
        sa.Column("moderation_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("rejected_at", sa.DateTime(timezone=True)),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('pending_payment','pending_review','active','rejected','cancelled')", name="ck_commercial_ad_status"),
        sa.CheckConstraint("payment_status IN ('unpaid','pending','paid','failed','refunded')", name="ck_commercial_ad_payment"),
        sa.CheckConstraint("destination_type IN ('website','phone','whatsapp','email')", name="ck_commercial_ad_destination"),
    )
    op.create_index("ix_commercial_advertisements_owner_user_id", "commercial_advertisements", ["owner_user_id"])
    op.create_index("ix_commercial_advertisements_image_asset_id", "commercial_advertisements", ["image_asset_id"])
    op.create_index("ix_commercial_ad_homepage", "commercial_advertisements", ["placement", "status", "payment_status", "admin_priority"])


def downgrade() -> None:
    op.drop_index("ix_commercial_ad_homepage", table_name="commercial_advertisements")
    op.drop_index("ix_commercial_advertisements_image_asset_id", table_name="commercial_advertisements")
    op.drop_index("ix_commercial_advertisements_owner_user_id", table_name="commercial_advertisements")
    op.drop_table("commercial_advertisements")
    # PostgreSQL enum values cannot safely be removed without rebuilding the
    # type. Keeping an unused value makes rollback non-destructive.
