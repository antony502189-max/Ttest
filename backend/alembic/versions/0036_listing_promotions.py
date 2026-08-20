"""Add persistent admin-controlled listing promotions.

Revision ID: 0036_listing_promotions
Revises: 0035_room_floor
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0036_listing_promotions"
down_revision: str | None = "0035_room_floor"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "listing_promotions",
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("boosted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("boosted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["boosted_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("listing_id"),
    )
    op.create_index("ix_listing_promotions_boosted_at", "listing_promotions", ["boosted_at"], unique=False)
    op.create_index("ix_listing_promotions_boosted_by", "listing_promotions", ["boosted_by"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_listing_promotions_boosted_by", table_name="listing_promotions")
    op.drop_index("ix_listing_promotions_boosted_at", table_name="listing_promotions")
    op.drop_table("listing_promotions")
