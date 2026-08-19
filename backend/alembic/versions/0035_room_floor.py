"""Add a structured floor value to room details.

Revision ID: 0035_room_floor
Revises: 0034_room_first_listing_details
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0035_room_floor"
down_revision: str | None = "0034_room_first_listing_details"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("listing_room_details", sa.Column("floor", sa.String(length=16), nullable=True))
    op.create_check_constraint("ck_room_details_floor", "listing_room_details", "floor IS NULL OR floor IN ('basement', '1', '2', '3', '4+', 'top')")


def downgrade() -> None:
    op.drop_constraint("ck_room_details_floor", "listing_room_details", type_="check")
    op.drop_column("listing_room_details", "floor")
