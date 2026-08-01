"""add pending role for first Google sign-in

Revision ID: 0024_google_role_selection
Revises: 0023_mail_worker_state
"""

from alembic import op


revision = "0024_google_role_selection"
down_revision = "0023_mail_worker_state"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'pending'")


def downgrade():
    # PostgreSQL enum values cannot be removed safely in-place.  Existing rows
    # must be resolved before a downgrade can be attempted.
    pass
