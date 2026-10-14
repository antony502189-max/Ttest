"""Preserve legacy day packages while recording calendar-month TOP orders."""
from alembic import op
import sqlalchemy as sa

revision = '0061_monthly_top'
down_revision = '0060_homepage_purchases'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('payment_orders', sa.Column('duration_months', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('payment_orders', 'duration_months')
