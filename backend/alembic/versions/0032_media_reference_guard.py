"""Guard listing-image references at the database boundary.

Revision ID: 0032_media_reference_guard
Revises: 0031_message_sender_rate_index
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0032_media_reference_guard"
down_revision: str | None = "0031_message_sender_rate_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


FUNCTION_NAME = "ensure_active_listing_image_asset"
TRIGGER_NAME = "trg_listing_images_active_asset"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE FUNCTION {FUNCTION_NAME}()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            asset_kind text;
        BEGIN
            SELECT kind
              INTO asset_kind
              FROM media_assets
             WHERE id = NEW.media_asset_id
               AND deleted_at IS NULL
             FOR UPDATE;

            IF NOT FOUND OR asset_kind <> 'listing_image' THEN
                RAISE EXCEPTION 'listing image asset must be active and have listing_image kind'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {TRIGGER_NAME}
        BEFORE INSERT OR UPDATE OF media_asset_id ON listing_images
        FOR EACH ROW
        EXECUTE FUNCTION {FUNCTION_NAME}()
        """
    )
    op.execute(
        """
        DELETE FROM listing_images AS listing_image
        USING media_assets AS asset
        WHERE listing_image.media_asset_id = asset.id
          AND (asset.deleted_at IS NOT NULL OR asset.kind <> 'listing_image')
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {TRIGGER_NAME} ON listing_images")
    op.execute(f"DROP FUNCTION IF EXISTS {FUNCTION_NAME}()")
