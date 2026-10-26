"""Durable inert fact queue, generations and rematch signals; no activation."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0070_ai_fact_pipeline"
down_revision = "0069_ai_listing_facts"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_fact_catalogs",
        sa.Column("canonical_listing_id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.CheckConstraint("revision >= 0", name="ck_ai_catalog_revision"),
    )
    op.create_table(
        "ai_fact_sources",
        sa.Column("source_record_id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_listing_id", pg.UUID(as_uuid=True), sa.ForeignKey("ai_fact_catalogs.canonical_listing_id"), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("source_fingerprint", sa.String(64), nullable=False),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column("source_status", sa.String(16), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("taxonomy_version", sa.String(32), nullable=False),
        sa.Column("extractor_version", sa.String(64), nullable=False),
        sa.Column("batch_id", pg.UUID(as_uuid=True), sa.ForeignKey("ai_listing_fact_batches.id")),
        sa.CheckConstraint("generation > 0", name="ck_ai_source_generation"),
        sa.CheckConstraint("content_hash ~ '^[0-9a-f]{64}$' AND source_fingerprint ~ '^[0-9a-f]{64}$' "
                           "AND snapshot_hash ~ '^[0-9a-f]{64}$'", name="ck_ai_source_hashes"),
        sa.CheckConstraint("source_status IN ('active','unknown','unavailable','retired')", name="ck_ai_source_status"),
        sa.CheckConstraint("schema_version = 'ai-facts.v1' AND taxonomy_version = 'ai-search.v1'", name="ck_ai_source_versions"),
        sa.CheckConstraint("extractor_version ~ '^[a-zA-Z0-9][a-zA-Z0-9._-]*$'", name="ck_ai_source_extractor"),
    )
    op.create_index("ix_ai_source_canonical", "ai_fact_sources", ["canonical_listing_id"])
    op.create_table(
        "ai_fact_jobs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_record_id", pg.UUID(as_uuid=True), sa.ForeignKey("ai_fact_sources.source_record_id"), nullable=False),
        sa.Column("canonical_listing_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("taxonomy_version", sa.String(32), nullable=False),
        sa.Column("extractor_version", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("fence", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result_revision", sa.Integer()),
        sa.Column("result_hash", sa.String(64)),
        sa.Column("failure_code", sa.String(32)),
        sa.UniqueConstraint("source_record_id", "generation", name="uq_ai_job_generation"),
        sa.CheckConstraint("generation > 0 AND fence >= 0 AND attempts >= 0", name="ck_ai_job_counters"),
        sa.CheckConstraint("status IN ('pending','running','succeeded','failed','superseded')", name="ck_ai_job_status"),
        sa.CheckConstraint("(status = 'running') = (lease_until IS NOT NULL)", name="ck_ai_job_lease"),
        sa.CheckConstraint("content_hash ~ '^[0-9a-f]{64}$' AND snapshot_hash ~ '^[0-9a-f]{64}$'", name="ck_ai_job_hash"),
        sa.CheckConstraint("schema_version = 'ai-facts.v1' AND taxonomy_version = 'ai-search.v1'", name="ck_ai_job_versions"),
        sa.CheckConstraint("extractor_version ~ '^[a-zA-Z0-9][a-zA-Z0-9._-]*$'", name="ck_ai_job_extractor"),
        sa.CheckConstraint("(status = 'succeeded' AND result_revision IS NOT NULL AND result_hash IS NOT NULL) OR "
                           "(status <> 'succeeded' AND result_revision IS NULL AND result_hash IS NULL)", name="ck_ai_job_result"),
        sa.CheckConstraint("result_revision IS NULL OR result_revision > 0", name="ck_ai_job_revision"),
        sa.CheckConstraint("result_hash IS NULL OR result_hash ~ '^[0-9a-f]{64}$'", name="ck_ai_job_result_hash"),
        sa.CheckConstraint("failure_code IS NULL OR failure_code IN ('EXTRACTOR_FAILED','INVALID_RESULT','ATTEMPTS_EXHAUSTED')", name="ck_ai_job_failure"),
    )
    op.create_index("ix_ai_job_claim", "ai_fact_jobs", ["available_at", "id"],
                    postgresql_where=sa.text("status IN ('pending','running')"))
    op.create_table(
        "ai_fact_rematch_events",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_listing_id", pg.UUID(as_uuid=True), sa.ForeignKey("ai_fact_catalogs.canonical_listing_id"), nullable=False),
        sa.Column("feature_revision", sa.Integer(), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("canonical_listing_id", "feature_revision", name="uq_ai_rematch_revision"),
        sa.CheckConstraint("feature_revision > 0", name="ck_ai_rematch_revision"),
        sa.CheckConstraint("input_hash ~ '^[0-9a-f]{64}$'", name="ck_ai_rematch_hash"),
    )


def downgrade():
    # Keep durable job, provenance and revision history on binary rollback.
    pass
