"""separate exact listing address data from public map data"""

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geography


revision = "0007_listing_private_location"
down_revision = "0006_search_history"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("listings", sa.Column("street", sa.String(160), nullable=False, server_default=""))
    op.add_column("listings", sa.Column("postcode", sa.String(32), nullable=False, server_default=""))
    op.add_column("listings", sa.Column("exact_location", Geography("POINT", srid=4326), nullable=True))


def downgrade():
    op.drop_column("listings", "exact_location")
    op.drop_column("listings", "postcode")
    op.drop_column("listings", "street")
