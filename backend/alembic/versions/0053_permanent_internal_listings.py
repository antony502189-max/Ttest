"""Make internal listings permanent and restore rows closed by the retired expiry policy.

Revision ID: 0053_permanent_internal_listings
Revises: 0052_commercial_advertisements
"""

from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision = "0053_permanent_internal_listings"
down_revision = "0052_commercial_advertisements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Restore only listings that the old automatic-expiry policy closed.

    Manually closed, hidden, rejected, deleted, blocked/restricted and external
    listings keep their existing lifecycle state. The legacy expires_at column
    remains for rollback compatibility but is cleared for all internal rows.
    """
    connection = op.get_bind()
    now = datetime.now(UTC)
    expired_rows = connection.execute(
        sa.text(
            """
            SELECT id
            FROM listings
            WHERE status = 'closed'
              AND closed_reason = 'expired'
              AND is_external IS FALSE
              AND deleted_at IS NULL
            FOR UPDATE
            """
        )
    ).mappings().all()

    for row in expired_rows:
        connection.execute(
            sa.text(
                """
                UPDATE listings
                SET status = 'published',
                    closed_reason = NULL,
                    expires_at = NULL,
                    published_at = COALESCE(published_at, :now),
                    updated_at = :now
                WHERE id = :listing_id
                """
            ),
            {"listing_id": row["id"], "now": now},
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO listing_status_history
                    (id, listing_id, from_status, to_status, changed_by, created_at)
                VALUES
                    (CAST(:history_id AS uuid), :listing_id, 'closed', 'published', NULL, :now)
                """
            ),
            {"history_id": str(uuid4()), "listing_id": row["id"], "now": now},
        )

    cleared = connection.execute(
        sa.text(
            """
            UPDATE listings
            SET expires_at = NULL
            WHERE is_external IS FALSE
              AND expires_at IS NOT NULL
            """
        )
    ).rowcount

    if expired_rows or cleared:
        connection.execute(
            sa.text(
                """
                UPDATE catalog_state
                SET version = version + 1,
                    updated_at = :now
                WHERE id = 1
                """
            ),
            {"now": now},
        )


def downgrade() -> None:
    # Irreversible data repair by design: recreating arbitrary expiry dates or
    # re-closing restored listings would discard legitimate post-upgrade state.
    pass
