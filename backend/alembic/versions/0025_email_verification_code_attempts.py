"""track email verification code attempts

Revision ID: 0025_email_verification_code_attempts
Revises: 0024_google_role_selection
"""

import sqlalchemy as sa
from alembic import op


revision = "0025_email_verification_code_attempts"
down_revision = "0024_google_role_selection"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("email_verification_tokens", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.alter_column("email_verification_tokens", "attempts", server_default=None)


def downgrade():
    op.drop_column("email_verification_tokens", "attempts")
