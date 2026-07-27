"""preserve imported demo listing images without treating them as uploads"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0010_legacy_listing_images"
down_revision = "0009_listing_views"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "listings",
        sa.Column("external_image_urls", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade():
    op.drop_column("listings", "external_image_urls")
