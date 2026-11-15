"""Fenced in-app notification scan, independent of foreground model quota."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0080_ai_saved_rematch"
down_revision = "0079_ai_operating_policy"
branch_labels = None
depends_on = None


def upgrade():
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table("ai_saved_rematch",
        sa.Column("saved_search_id", uuid, sa.ForeignKey("ai_saved_searches.saved_search_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("next_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("cursor_listing_id", uuid),
        sa.Column("fence", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("lease_token", uuid),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.CheckConstraint("fence >= 0", name="ck_ai_saved_rematch_fence"),
        sa.CheckConstraint("(lease_token IS NULL) = (lease_until IS NULL)", name="ck_ai_saved_rematch_lease"))
    op.create_index("ix_ai_saved_rematch_next_at", "ai_saved_rematch", ["next_at"])
    op.create_table("ai_saved_seen",
        sa.Column("saved_search_id", uuid, sa.ForeignKey("ai_saved_searches.saved_search_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("listing_id", uuid, sa.ForeignKey("listings.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))


def downgrade():
    raise RuntimeError("SCHEMA_DOWNGRADE_DISABLED: preserve saved notification deduplication")
