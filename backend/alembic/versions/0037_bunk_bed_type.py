"""Add expand-compatible bunk bed storage.

Revision ID: 0037_bunk_bed_type
Revises: 0036_listing_promotions
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0037_bunk_bed_type"
down_revision: str | None = "0036_listing_promotions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Expand-only: preserve the constrained legacy bed_type column so both the
    # previous and new application releases can overlap safely during deployment.
    op.add_column(
        "listing_room_details",
        sa.Column("bed_type_v2", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("listing_room_details", "bed_type_v2")