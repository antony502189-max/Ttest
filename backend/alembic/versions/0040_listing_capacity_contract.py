"""align listing room capacity with the API contract

Revision ID: 0040_listing_capacity_contract
Revises: 0039_admin_grant_repair
"""

from alembic import op

revision = "0040_listing_capacity_contract"
down_revision = "0039_admin_grant_repair"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Both historical constraints cap capacity at two, while the publication
    # and patch schemas deliberately support shared rooms with up to ten places.
    op.drop_constraint("ck_listings_room_capacity", "listings", type_="check")
    op.drop_constraint("ck_listings_room_capacity_range", "listings", type_="check")
    op.create_check_constraint(
        "ck_listings_room_capacity_range",
        "listings",
        "room_capacity BETWEEN 1 AND 10",
    )


def downgrade() -> None:
    # A downgrade cannot preserve rows above the former limit. Normalize them
    # explicitly before restoring the old database contract.
    op.execute("UPDATE listings SET room_capacity = 2 WHERE room_capacity > 2")
    op.drop_constraint("ck_listings_room_capacity_range", "listings", type_="check")
    op.create_check_constraint(
        "ck_listings_room_capacity_range",
        "listings",
        "room_capacity BETWEEN 1 AND 2",
    )
    op.create_check_constraint(
        "ck_listings_room_capacity",
        "listings",
        "room_capacity IN (1, 2)",
    )
