"""Apply a financial inbox receipt once, preserving later operator resolutions."""
from alembic import op
import sqlalchemy as sa

revision = "0063_financial_inbox_receipts"
down_revision = "0062_payment_audit"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("payment_events",sa.Column("applied_at",sa.DateTime(timezone=True),nullable=True))


def downgrade():
    op.drop_column("payment_events","applied_at")
