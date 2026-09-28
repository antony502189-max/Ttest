"""Indexes for bounded public search and geography viewport queries.

Revision ID: 0050_spain_search_indexes
Revises: 0049_listing_video
"""

from alembic import op

revision = "0050_spain_search_indexes"
down_revision = "0049_listing_video"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # CONCURRENTLY avoids blocking writes to a populated listings table.
    with op.get_context().autocommit_block():
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_listings_public_created_keyset "
            "ON listings (rental_mode, created_at DESC, id) "
            "WHERE status = 'published' AND deleted_at IS NULL"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_listings_public_city_trgm "
            "ON listings USING gin (city gin_trgm_ops) "
            "WHERE status = 'published' AND deleted_at IS NULL"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_listings_public_area_trgm "
            "ON listings USING gin (area gin_trgm_ops) "
            "WHERE status = 'published' AND deleted_at IS NULL"
        )
    # ix_listings_location is the existing geography GiST index used by
    # ST_Intersects(location, viewport) and ST_DWithin(location, center).


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for name in (
            "ix_listings_public_area_trgm",
            "ix_listings_public_city_trgm",
            "ix_listings_public_created_keyset",
        ):
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
