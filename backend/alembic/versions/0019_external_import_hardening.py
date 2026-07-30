"""preserve complete external listing details and source run state

Revision ID: 0019_external_import_hardening
Revises: 0018_media_perceptual_hash
"""

from alembic import op

revision = "0019_external_import_hardening"
down_revision = "0018_media_perceptual_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in (
        "deposit_amount",
        "bills_included",
        "bathroom",
        "kitchen",
        "furnished",
        "room_size_m2",
        "room_capacity",
        "tenant_requirement",
        "advertiser_type",
    ):
        op.execute(f"ALTER TABLE listings ALTER COLUMN {column} DROP NOT NULL")
    op.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS deposit_text varchar(240)")
    op.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS bills_text varchar(240)")
    op.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS advertiser_name varchar(160)")
    op.execute("ALTER TABLE external_import_runs ADD COLUMN IF NOT EXISTS challenge_type varchar(64)")
    op.execute("ALTER TABLE external_import_runs ADD COLUMN IF NOT EXISTS http_status integer")
    op.execute("ALTER TABLE external_import_runs ADD COLUMN IF NOT EXISTS final_url text")
    op.execute("ALTER TABLE external_import_runs ADD COLUMN IF NOT EXISTS next_check_at timestamptz")
    op.execute("ALTER TABLE external_import_runs ADD COLUMN IF NOT EXISTS diagnostic_paths jsonb NOT NULL DEFAULT '{}'::jsonb")
    op.execute("CREATE INDEX IF NOT EXISTS ix_external_import_runs_next_check_at ON external_import_runs (next_check_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_external_import_runs_next_check_at")
    for column in ("challenge_type", "http_status", "final_url", "next_check_at", "diagnostic_paths"):
        op.execute(f"ALTER TABLE external_import_runs DROP COLUMN IF EXISTS {column}")
    for column in ("deposit_text", "bills_text", "advertiser_name"):
        op.execute(f"ALTER TABLE listings DROP COLUMN IF EXISTS {column}")
