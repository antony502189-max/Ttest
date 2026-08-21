"""Allow bunk beds in structured room details.

Revision ID: 0037_bunk_bed_type
Revises: 0036_listing_promotions
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0037_bunk_bed_type"
down_revision: str | None = "0036_listing_promotions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_room_details_bed_type", "listing_room_details", type_="check")
    op.create_check_constraint(
        "ck_room_details_bed_type",
        "listing_room_details",
        "bed_type IS NULL OR bed_type IN ('single', 'double', 'bunk')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_room_details_bed_type", "listing_room_details", type_="check")
    op.create_check_constraint(
        "ck_room_details_bed_type",
        "listing_room_details",
        "bed_type IS NULL OR bed_type IN ('single', 'double')",
    )
