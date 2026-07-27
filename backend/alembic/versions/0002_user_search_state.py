"""user favorites, discarded listings and saved searches"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_user_search_state"
down_revision = "0001_core"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "favorites",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("listing_id", sa.Uuid(), sa.ForeignKey("listings.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "listing_id", name="uq_favorites_user_listing"),
    )
    op.create_table(
        "discarded_listings",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("listing_id", sa.Uuid(), sa.ForeignKey("listings.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "listing_id", name="uq_discarded_user_listing"),
    )
    op.create_table(
        "saved_searches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False, server_default=""),
        sa.Column("query", sa.String(240), nullable=False, server_default=""),
        sa.Column(
            "rental_mode",
            postgresql.ENUM("long", "holiday", name="rental_mode", create_type=False),
            nullable=False,
        ),
        sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("polygon", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("alerts_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_saved_searches_user_id", "saved_searches", ["user_id"])


def downgrade():
    op.drop_table("saved_searches")
    op.drop_table("discarded_listings")
    op.drop_table("favorites")
