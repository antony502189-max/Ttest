"""Allow server-authorized complimentary advertising without recording a payment."""
import sqlalchemy as sa

from alembic import op

revision = "0066_complimentary_ads"
down_revision = "0065_verified_geography"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("commercial_advertisements", sa.Column("payment_waived", sa.Boolean(), nullable=True))


def downgrade():
    # Existing complimentary campaigns must remain readable after a rollback.
    pass
