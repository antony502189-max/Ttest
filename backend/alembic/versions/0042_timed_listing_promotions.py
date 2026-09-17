"""add timed windows and price snapshots to listing promotions

Revision ID: 0042_timed_listing_promotions
Revises: 0041_direct_publish_pending
"""

import sqlalchemy as sa

from alembic import op

revision = "0042_timed_listing_promotions"
down_revision = "0041_direct_publish_pending"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Expand-compatible with the previous release: starts_at has a server
    # default so the old application can still insert a promotion while a
    # rolling deployment is in progress. Existing rows retain their historical
    # boost timestamp as the beginning of the promotion window.
    op.add_column(
        "listing_promotions",
        sa.Column("starts_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column(
        "listing_promotions",
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "listing_promotions",
        sa.Column("daily_price_cents", sa.Integer(), nullable=True),
    )
    op.add_column(
        "listing_promotions",
        sa.Column("total_price_cents", sa.Integer(), nullable=True),
    )
    op.execute("UPDATE listing_promotions SET starts_at = boosted_at")
    op.create_index("ix_listing_promotions_starts_at", "listing_promotions", ["starts_at"], unique=False)
    op.create_index("ix_listing_promotions_ends_at", "listing_promotions", ["ends_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_listing_promotions_ends_at", table_name="listing_promotions")
    op.drop_index("ix_listing_promotions_starts_at", table_name="listing_promotions")
    op.drop_column("listing_promotions", "total_price_cents")
    op.drop_column("listing_promotions", "daily_price_cents")
    op.drop_column("listing_promotions", "ends_at")
    op.drop_column("listing_promotions", "starts_at")
