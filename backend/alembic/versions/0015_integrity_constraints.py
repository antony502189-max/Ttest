"""enforce listing integrity and common search indexes

Revision ID: 0015_integrity_constraints
Revises: 0014_session_audit
"""

from alembic import op

revision = "0015_integrity_constraints"
down_revision = "0014_session_audit"
branch_labels = None
depends_on = None


CONSTRAINTS = {
    "ck_listings_weekly_price_nonnegative": "weekly_price IS NULL OR weekly_price >= 0",
    "ck_listings_deposit_nonnegative": "deposit_amount >= 0",
    "ck_listings_room_size_positive": "room_size_m2 >= 1",
    "ck_listings_bedroom_count_range": "bedroom_count IS NULL OR bedroom_count BETWEEN 1 AND 99",
    "ck_listings_current_residents_nonnegative": "current_residents >= 0",
    "ck_listings_room_capacity_range": "room_capacity BETWEEN 1 AND 2",
    "ck_listings_minimum_stay_nonnegative": "minimum_stay_months >= 0",
    "ck_listings_minimum_nights_nonnegative": "minimum_nights IS NULL OR minimum_nights >= 0",
    "ck_listings_dates_ordered": "available_until IS NULL OR available_from IS NULL OR available_until >= available_from",
    "ck_listings_primary_price_for_mode": "(rental_mode = 'long' AND monthly_price IS NOT NULL) OR (rental_mode = 'holiday' AND nightly_price IS NOT NULL)",
}


def upgrade() -> None:
    for name, expression in CONSTRAINTS.items():
        op.create_check_constraint(name, "listings", expression)

    # Partial/composite indexes follow the public search and owner dashboard paths.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_listings_public_search "
        "ON listings (rental_mode, published_at DESC, id) "
        "WHERE status = 'published' AND deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_listings_owner_active "
        "ON listings (owner_user_id, created_at DESC) WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_listings_bedroom_count "
        "ON listings (bedroom_count) WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_mail_outbox_pending "
        "ON mail_outbox (created_at, id) WHERE status = 'pending'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_mail_outbox_pending")
    op.execute("DROP INDEX IF EXISTS ix_listings_bedroom_count")
    op.execute("DROP INDEX IF EXISTS ix_listings_owner_active")
    op.execute("DROP INDEX IF EXISTS ix_listings_public_search")
    for name in reversed(tuple(CONSTRAINTS)):
        op.drop_constraint(name, "listings", type_="check")
