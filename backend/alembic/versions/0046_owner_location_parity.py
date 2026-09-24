"""align owner-created public map coordinates with saved exact locations

Revision ID: 0046_owner_location_parity
Revises: 0045_habitaclia_location_fix
"""

from alembic import op

revision = "0046_owner_location_parity"
down_revision = "0045_habitaclia_location_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE listings
        SET location = exact_location,
            approximate_address = regexp_replace(
                approximate_address,
                '\\s*·\\s*ubicación aproximada$',
                ' · ubicación en el mapa',
                'i'
            )
        WHERE is_external IS FALSE
          AND exact_location IS NOT NULL
        """
    )
    op.execute("UPDATE catalog_state SET version = version + 1, updated_at = NOW() WHERE id = 1")


def downgrade() -> None:
    # The previous randomized public coordinates cannot be reconstructed from
    # exact_location alone because their historic offset seed/contract is no
    # longer part of the database. Keep truthful coordinates on downgrade.
    pass
