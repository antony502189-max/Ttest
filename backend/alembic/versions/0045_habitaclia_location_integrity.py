"""remove unverified Habitaclia viewport markers

Revision ID: 0045_habitaclia_location_integrity
Revises: 0044_nullable_listing_location
"""

from alembic import op

revision = "0045_habitaclia_location_integrity"
down_revision = "0044_nullable_listing_location"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Habitaclia's public static-map center is a viewport center, not a
    # verified dwelling coordinate. Remove already-persisted markers
    # immediately; the public card remains published because location is
    # nullable since revision 0044.
    op.execute(
        """
        UPDATE listings
        SET location = NULL
        WHERE is_external IS TRUE
          AND primary_source = 'Habitaclia'
          AND location IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE external_listing_sources
        SET normalized_payload = jsonb_set(
                jsonb_set(normalized_payload, '{latitude}', 'null'::jsonb, true),
                '{longitude}', 'null'::jsonb, true
            ),
            last_error = 'source_location_unverified'
        WHERE source_name = 'Habitaclia'
          AND current_status = 'active'
        """
    )


def downgrade() -> None:
    # Do not recreate coordinates that were never verified as property
    # coordinates. A later source refresh may repopulate a marker only from a
    # stronger source signal.
    pass
