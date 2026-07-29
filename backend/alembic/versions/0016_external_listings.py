"""external listing import support

Revision ID: 0016_external_listings
Revises: 0015_integrity_constraints
"""

from alembic import op

revision = "0016_external_listings"
down_revision = "0015_integrity_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS is_external boolean NOT NULL DEFAULT false")
    op.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS primary_source varchar(64)")
    op.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS primary_source_url text")
    op.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS source_price_text varchar(120)")
    op.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS source_price_currency varchar(8)")
    op.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS source_price_period varchar(16)")
    op.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS source_price_is_from boolean")
    op.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS external_contact_phone varchar(64)")
    op.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS external_contact_whatsapp varchar(64)")
    op.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS external_contact_email varchar(320)")
    op.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS imported_at timestamptz")
    op.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS last_synced_at timestamptz")
    op.execute("ALTER TABLE listings ALTER COLUMN smoking_allowed DROP NOT NULL")
    op.execute("ALTER TABLE listings ALTER COLUMN pets_allowed DROP NOT NULL")
    op.execute("ALTER TABLE listings ALTER COLUMN children_allowed DROP NOT NULL")
    op.execute("ALTER TABLE listings ALTER COLUMN empadronamiento_allowed DROP NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_listings_is_external ON listings (is_external)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_listings_primary_source ON listings (primary_source)")
    op.execute("""
      CREATE TABLE IF NOT EXISTS external_listing_sources (
        id uuid PRIMARY KEY,
        source_name varchar(64) NOT NULL,
        external_id varchar(255) NOT NULL,
        source_url text NOT NULL,
        canonical_listing_id uuid NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
        raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
        fingerprint varchar(64) NOT NULL,
        source_price_text varchar(120),
        first_seen_at timestamptz NOT NULL DEFAULT now(), last_seen_at timestamptz,
        last_checked_at timestamptz, last_success_at timestamptz, content_updated_at timestamptz,
        consecutive_missing_runs integer NOT NULL DEFAULT 0, current_status varchar(32) NOT NULL DEFAULT 'active', last_error text,
        CONSTRAINT uq_external_listing_source_external_id UNIQUE (source_name, external_id),
        CONSTRAINT uq_external_listing_source_url UNIQUE (source_url)
      )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_external_listing_sources_source_name ON external_listing_sources (source_name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_external_listing_sources_canonical_listing_id ON external_listing_sources (canonical_listing_id)")
    op.execute("""
      CREATE TABLE IF NOT EXISTS external_import_runs (
        id uuid PRIMARY KEY, run_id varchar(64) NOT NULL, source_name varchar(64) NOT NULL,
        started_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz, result varchar(32) NOT NULL DEFAULT 'running',
        counters jsonb NOT NULL DEFAULT '{}'::jsonb, last_error text
      )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_external_import_runs_run_id ON external_import_runs (run_id)")


def downgrade() -> None:
    op.drop_table("external_import_runs")
    op.drop_table("external_listing_sources")
    for column in ("last_synced_at", "imported_at", "external_contact_email", "external_contact_whatsapp", "external_contact_phone", "source_price_is_from", "source_price_period", "source_price_currency", "source_price_text", "primary_source_url", "primary_source", "is_external"):
        op.execute(f"ALTER TABLE listings DROP COLUMN IF EXISTS {column}")
