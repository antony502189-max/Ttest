"""preserve unknown external stay and restriction values

Revision ID: 0017_nullable_external_unknowns
Revises: 0016_external_listings
"""

from alembic import op

revision = "0017_nullable_external_unknowns"
down_revision = "0016_external_listings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE listings ALTER COLUMN minimum_stay_months DROP NOT NULL")


def downgrade() -> None:
    op.execute("UPDATE listings SET minimum_stay_months = 0 WHERE minimum_stay_months IS NULL")
    op.execute("ALTER TABLE listings ALTER COLUMN minimum_stay_months SET NOT NULL")
