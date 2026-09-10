"""publish existing internal listings that were waiting for moderation

Revision ID: 0041_direct_publish_pending
Revises: 0040_listing_capacity_contract
"""

from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision = "0041_direct_publish_pending"
down_revision = "0040_listing_capacity_contract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Move legacy pre-publication pending rows into the direct-publish state.

    Only live, internal and non-expired listings are repaired. External imports
    already own their own lifecycle, while deleted/expired rows must remain
    non-public. A status-history row is written for every repaired listing so
    the one-time production change remains auditable.
    """
    connection = op.get_bind()
    now = datetime.now(UTC)
    rows = connection.execute(
        sa.text(
            """
            SELECT id, owner_user_id
            FROM listings
            WHERE status = 'pending'
              AND is_external IS FALSE
              AND deleted_at IS NULL
              AND (expires_at IS NULL OR expires_at > :now)
            FOR UPDATE
            """
        ),
        {"now": now},
    ).mappings().all()

    for row in rows:
        connection.execute(
            sa.text(
                """
                UPDATE listings
                SET status = 'published',
                    published_at = COALESCE(published_at, :now),
                    updated_at = :now
                WHERE id = :listing_id
                """
            ),
            {"now": now, "listing_id": row["id"]},
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO listing_status_history
                    (id, listing_id, from_status, to_status, changed_by, created_at)
                VALUES
                    (CAST(:history_id AS uuid), :listing_id, 'pending', 'published', :owner_user_id, :now)
                """
            ),
            {
                "history_id": str(uuid4()),
                "listing_id": row["id"],
                "owner_user_id": row["owner_user_id"],
                "now": now,
            },
        )

    if rows:
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
    # Deliberately irreversible as a data repair: after direct publication is
    # live, a published row cannot be distinguished safely from one that was
    # published by a user after this migration. The previous application can
    # still read and serve `published`, so rollback compatibility is preserved.
    pass
