"""add expand-compatible listing room capacity storage

Revision ID: 0040_listing_capacity_contract
Revises: 0039_admin_grant_repair
"""

import sqlalchemy as sa

from alembic import op

revision = "0040_listing_capacity_contract"
down_revision = "0039_admin_grant_repair"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Expand-only: preserve the constrained legacy listings.room_capacity so
    # the previous application release remains a valid rollback target. The new
    # release stores 1..10 here and mirrors a capped value into the old column.
    op.add_column(
        "listing_room_details",
        sa.Column("room_capacity_v2", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("listing_room_details", "room_capacity_v2")
