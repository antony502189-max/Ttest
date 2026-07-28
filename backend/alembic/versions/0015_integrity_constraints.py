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


def create_constraint_if_missing(name: str, expression: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = '{name}'
                  AND conrelid = 'listings'::regclass
            ) THEN
                ALTER TABLE listings
                ADD CONSTRAINT {name} CHECK ({expression});
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    # Existing local/demo databases may contain records created before these
    # invariants existed. Normalize them deterministically before validation.
    op.execute("UPDATE listings SET weekly_price = 0 WHERE weekly_price < 0")
    op.execute("UPDATE listings SET deposit_amount = 0 WHERE deposit_amount < 0")
    op.execute("UPDATE listings SET room_size_m2 = 1 WHERE room_size_m2 < 1")
    op.execute("UPDATE listings SET bedroom_count = LEAST(99, GREATEST(1, bedroom_count)) WHERE bedroom_count IS NOT NULL")
    op.execute("UPDATE listings SET current_residents = 0 WHERE current_residents < 0")
    op.execute("UPDATE listings SET room_capacity = LEAST(2, GREATEST(1, room_capacity))")
    op.execute("UPDATE listings SET minimum_stay_months = 0 WHERE minimum_stay_months < 0")
    op.execute("UPDATE listings SET minimum_nights = 0 WHERE minimum_nights < 0")
    op.execute("UPDATE listings SET available_until = NULL WHERE available_from IS NOT NULL AND available_until < available_from")
    op.execute(
        "UPDATE listings SET monthly_price = GREATEST(0, COALESCE(monthly_price, nightly_price, 0)) "
        "WHERE rental_mode = 'long' AND monthly_price IS NULL"
    )
    op.execute(
        "UPDATE listings SET nightly_price = GREATEST(0, COALESCE(nightly_price, monthly_price, 0)) "
        "WHERE rental_mode = 'holiday' AND nightly_price IS NULL"
    )

    for name, expression in CONSTRAINTS.items():
        create_constraint_if_missing(name, expression)

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
        op.execute(f"ALTER TABLE listings DROP CONSTRAINT IF EXISTS {name}")
