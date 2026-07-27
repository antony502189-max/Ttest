"""server search history"""

from alembic import op
import sqlalchemy as sa

revision = "0006_search_history"
down_revision = "0005_media_assets"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "search_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("normalized_query", sa.String(240), nullable=False),
        sa.Column("searched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_search_history_user_id", "search_history", ["user_id"])
    op.create_index("ix_search_history_normalized_query", "search_history", ["normalized_query"])
    op.create_index("ix_search_history_searched_at", "search_history", ["searched_at"])


def downgrade():
    op.drop_table("search_history")
