"""Re-assert permanent first-party listing policy after stale expiry-worker rollouts.

Revision ID: 0054_recover_reexpired
Revises: 0053_permanent_internal_listings
"""

from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision = "0054_recover_reexpired"
down_revision = "0053_permanent_internal_listings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Repair only first-party rows closed by the retired automatic expiry path.

    PR #261 removed automatic expiry for internal listings. A production node
    that was still running the previous release could nevertheless close a row
    after migration 0053 had already executed. Because Alembic migrations are
    one-shot, 0053 would not repair such a later closure on the next deploy.

    This follow-up repair is intentionally narrow:
    - internal listings only;
    - live (not deleted) rows only;
    - only status=closed + closed_reason=expired;
    - manually closed, hidden, rejected, restricted and external rows are not
      changed.

    The deploy procedure stops application writers before migrations, so once
    this repair runs under the expiry-free release there is no supported writer
    left that can recreate the retired state.
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
            SET expires_at = NULL,
                updated_at = CASE WHEN expires_at IS NOT NULL THEN :now ELSE updated_at END
            WHERE is_external IS FALSE
              AND expires_at IS NOT NULL
            """
        ),
        {"now": now},
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
    # Data repair is intentionally irreversible. Reconstructing retired expiry
    # timestamps or re-closing repaired listings would destroy legitimate state.
    pass
