"""allow list-only public listings without a map point

Revision ID: 0044_nullable_listing_location
Revises: 0043_homepage_hero_promotions
"""

from geoalchemy2 import Geography

from alembic import op

revision = "0044_nullable_listing_location"
down_revision = "0043_homepage_hero_promotions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "listings",
        "location",
        existing_type=Geography("POINT", srid=4326),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "listings",
        "location",
        existing_type=Geography("POINT", srid=4326),
        nullable=False,
    )
