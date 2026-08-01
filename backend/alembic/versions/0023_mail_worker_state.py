"""track mail worker heartbeats for health checks

Revision ID: 0023_mail_worker_state
Revises: 0022_unknown_state_counter
"""

from alembic import op

revision = "0023_mail_worker_state"
down_revision = "0022_unknown_state_counter"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS mail_worker_state (
            id integer PRIMARY KEY,
            health varchar(16) NOT NULL DEFAULT 'healthy',
            heartbeat_at timestamptz,
            last_success_at timestamptz,
            last_error text
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_mail_worker_state_health ON mail_worker_state (health)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_mail_worker_state_heartbeat_at ON mail_worker_state (heartbeat_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS mail_worker_state")
