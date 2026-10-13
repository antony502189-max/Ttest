"""One-shot advertising vacancy alerts; retain existing paid ad packages."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "0058_advertising_waitlist"
down_revision = "0057_payment_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payment_orders", sa.Column("last_reconciled_at", sa.DateTime(timezone=True)))
    op.create_table(
        "advertising_waitlist",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("subscription", postgresql.JSONB()),
        sa.Column("language", sa.String(2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("notified_at", sa.DateTime(timezone=True)),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("advertising_waitlist")
    op.drop_column("payment_orders", "last_reconciled_at")
