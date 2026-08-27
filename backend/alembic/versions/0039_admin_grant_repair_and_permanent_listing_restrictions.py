"""Repair designated administrator grants and allow permanent listing restrictions.

Revision ID: 0039_admin_grant_repair
Revises: 0038_notifications

The original 0033 migration intentionally skipped legacy-blocked accounts when
seeding admin_access.  That was safe for the conversion, but it made an old
account state permanently suppress either required administrator.  This
forward-only repair restores the allowlist *grant* for both designated emails;
it does not resurrect, unblock, unrestrict, or link any user.  require_admin
continues to enforce the Google identity and account-safety checks at runtime.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0039_admin_grant_repair"
down_revision: str | None = "0038_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REQUIRED_ADMIN_EMAILS = ("antony502189@gmail.com", "tf.shuler@gmail.com")


def upgrade() -> None:
    connection = op.get_bind()
    # This is idempotent across the four historical states: absent, present,
    # inactive, and present for a user which is not yet Google-linked.
    for email in REQUIRED_ADMIN_EMAILS:
        connection.execute(
            sa.text(
                """
                INSERT INTO admin_access (email, active)
                VALUES (:email, TRUE)
                ON CONFLICT (email) DO UPDATE SET active = TRUE
                """
            ),
            {"email": email},
        )

    op.drop_constraint("ck_listing_restrictions_dates", "listing_restrictions", type_="check")
    op.alter_column("listing_restrictions", "ends_at", existing_type=sa.DateTime(timezone=True), nullable=True)
    op.create_check_constraint(
        "ck_listing_restrictions_dates",
        "listing_restrictions",
        "ends_at IS NULL OR ends_at > starts_at",
    )


def downgrade() -> None:
    # A downgrade cannot faithfully encode active permanent restrictions in the
    # old schema.  Fail closed instead of fabricating an expiry timestamp.
    connection = op.get_bind()
    active_permanent = connection.scalar(
        sa.text("SELECT 1 FROM listing_restrictions WHERE revoked_at IS NULL AND ends_at IS NULL LIMIT 1")
    )
    if active_permanent:
        raise RuntimeError("Revoke permanent listing restrictions before downgrading 0039")
    op.drop_constraint("ck_listing_restrictions_dates", "listing_restrictions", type_="check")
    op.alter_column("listing_restrictions", "ends_at", existing_type=sa.DateTime(timezone=True), nullable=False)
    op.create_check_constraint("ck_listing_restrictions_dates", "listing_restrictions", "ends_at > starts_at")
