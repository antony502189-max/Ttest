"""Allow server-authorized complimentary advertising without recording a payment."""
from alembic import op

revision = "0066_complimentary_ads"
down_revision = "0065_verified_geography"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_commercial_ad_payment", "commercial_advertisements", type_="check")
    op.create_check_constraint("ck_commercial_ad_payment", "commercial_advertisements",
                               "payment_status IN ('unpaid','pending','paid','failed','refunded','waived')")


def downgrade():
    # Existing complimentary campaigns must remain readable after a rollback.
    pass
