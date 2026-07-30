"""external discovery lifecycle, worker state and catalog version

Revision ID: 0020_external_lifecycle
Revises: 0019_external_import_hardening
"""

from alembic import op

revision = "0020_external_lifecycle"
down_revision = "0019_external_import_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE external_listing_sources ADD COLUMN IF NOT EXISTS normalized_payload jsonb NOT NULL DEFAULT '{}'::jsonb")
    op.execute("ALTER TABLE external_listing_sources ADD COLUMN IF NOT EXISTS removed_at timestamptz")
    op.execute("ALTER TABLE external_listing_sources ADD COLUMN IF NOT EXISTS removed_reason varchar(32)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_external_listing_sources_removed_at ON external_listing_sources (removed_at)")
    op.execute("ALTER TABLE external_import_runs ADD COLUMN IF NOT EXISTS discovery_complete boolean")
    op.execute("ALTER TABLE external_import_runs ADD COLUMN IF NOT EXISTS discovery_pages integer")
    op.execute("ALTER TABLE external_import_runs ADD COLUMN IF NOT EXISTS discovery_failed_pages jsonb NOT NULL DEFAULT '[]'::jsonb")
    op.execute("""CREATE TABLE IF NOT EXISTS external_worker_state (
        id integer PRIMARY KEY, health varchar(16) NOT NULL DEFAULT 'healthy', last_started_at timestamptz,
        last_finished_at timestamptz, last_success_at timestamptz, next_run_at timestamptz,
        heartbeat_at timestamptz, last_error text, last_run_id varchar(64))""")
    op.execute("""CREATE TABLE IF NOT EXISTS catalog_state (
        id integer PRIMARY KEY, version integer NOT NULL DEFAULT 1, updated_at timestamptz NOT NULL DEFAULT now())""")
    op.execute("INSERT INTO catalog_state (id, version, updated_at) VALUES (1, 1, now()) ON CONFLICT (id) DO NOTHING")
    op.execute("""CREATE OR REPLACE FUNCTION bump_catalog_version() RETURNS trigger AS $$
    BEGIN
      INSERT INTO catalog_state (id, version, updated_at) VALUES (1, 1, now())
      ON CONFLICT (id) DO UPDATE SET version = catalog_state.version + 1, updated_at = now();
      RETURN NEW;
    END; $$ LANGUAGE plpgsql""")
    op.execute("DROP TRIGGER IF EXISTS listings_catalog_version ON listings")
    op.execute("CREATE TRIGGER listings_catalog_version AFTER INSERT OR UPDATE OR DELETE ON listings FOR EACH ROW EXECUTE FUNCTION bump_catalog_version()")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS listings_catalog_version ON listings")
    op.execute("DROP FUNCTION IF EXISTS bump_catalog_version()")
    op.execute("DROP TABLE IF EXISTS catalog_state")
    op.execute("DROP TABLE IF EXISTS external_worker_state")
    op.execute("ALTER TABLE external_import_runs DROP COLUMN IF EXISTS discovery_failed_pages")
    op.execute("ALTER TABLE external_import_runs DROP COLUMN IF EXISTS discovery_pages")
    op.execute("ALTER TABLE external_import_runs DROP COLUMN IF EXISTS discovery_complete")
    op.execute("DROP INDEX IF EXISTS ix_external_listing_sources_removed_at")
    op.execute("ALTER TABLE external_listing_sources DROP COLUMN IF EXISTS removed_reason")
    op.execute("ALTER TABLE external_listing_sources DROP COLUMN IF EXISTS removed_at")
    op.execute("ALTER TABLE external_listing_sources DROP COLUMN IF EXISTS normalized_payload")
