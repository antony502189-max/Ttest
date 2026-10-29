"""Bind lifecycle command replay to its explicitly chosen initial rental mode."""
import sqlalchemy as sa
from alembic import op

revision = "0073_ai_command_seed"
down_revision = "0072_ai_session_commands"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ai_session_commands", sa.Column("seed_mode", sa.String(7), nullable=True))
    op.create_check_constraint("ck_ai_command_seed", "ai_session_commands",
                               "seed_mode IS NULL OR seed_mode IN ('long', 'holiday')")


def downgrade():
    # Expand-only: preserve recovery receipts and compatibility with old binaries.
    pass
