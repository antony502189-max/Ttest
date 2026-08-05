"""make catalog state increments monotonic under concurrent writes

Revision ID: 0026_catalog_state_concurrency
Revises: 0025_email_verification_codes
"""

from alembic import op

revision = "0026_catalog_state_concurrency"
down_revision = "0025_email_verification_codes"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        INSERT INTO catalog_state (id, version, updated_at)
        VALUES (1, 1, now())
        ON CONFLICT (id) DO NOTHING
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION ensure_catalog_state_version_increases()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.version <= OLD.version THEN
                NEW.version := OLD.version + 1;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER catalog_state_version_monotonic
        BEFORE UPDATE OF version ON catalog_state
        FOR EACH ROW
        EXECUTE FUNCTION ensure_catalog_state_version_increases()
        """
    )


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS catalog_state_version_monotonic ON catalog_state")
    op.execute("DROP FUNCTION IF EXISTS ensure_catalog_state_version_increases()")
