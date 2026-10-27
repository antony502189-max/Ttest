"""Add inert per-source facts and canonical projection; no backfill or activation.

Integrated after still-unreleased AI-07/08. This parent reconciliation must
land before any deployment of 0069; released migration history is unchanged.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0069_ai_listing_facts"
down_revision = "0068_ai_search_sessions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_listing_fact_batches",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_listing_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("source_record_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("source_generation", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("taxonomy_version", sa.String(32), nullable=False),
        sa.Column("extractor_version", sa.String(64), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_status", sa.String(16), nullable=False),
        sa.Column("last_successful_check_at", sa.DateTime(timezone=True)),
        sa.Column("last_content_change_at", sa.DateTime(timezone=True)),
        sa.Column("last_check_error_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("schema_version = 'ai-facts.v1' AND taxonomy_version = 'ai-search.v1'", name="ck_ai_batch_versions"),
        sa.CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="ck_ai_batch_hash"),
        sa.CheckConstraint("source_generation > 0", name="ck_ai_batch_generation"),
        sa.CheckConstraint("extractor_version ~ '^[a-zA-Z0-9][a-zA-Z0-9._-]*$'", name="ck_ai_batch_extractor"),
        sa.CheckConstraint("source_status IN ('active','unknown','unavailable','retired')", name="ck_ai_batch_status"),
        sa.CheckConstraint("last_successful_check_at <= observed_at AND last_content_change_at <= observed_at "
                           "AND last_check_error_at <= observed_at", name="ck_ai_batch_timestamps"),
    )
    op.create_index("ix_ai_batch_listing", "ai_listing_fact_batches", ["canonical_listing_id"])
    op.create_index("ix_ai_batch_source_generation", "ai_listing_fact_batches", ["source_record_id", "source_generation"])
    op.create_index("uq_ai_batch_identity", "ai_listing_fact_batches", [
        "canonical_listing_id", sa.text("(source_record_id IS NULL)"),
        sa.text("coalesce(source_record_id, canonical_listing_id)"),
        "source_generation", "content_hash", "extractor_version", "schema_version", "taxonomy_version",
    ], unique=True)
    op.create_table(
        "ai_listing_facts",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", pg.UUID(as_uuid=True), sa.ForeignKey("ai_listing_fact_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(32), nullable=False),
        sa.Column("scope_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("typed_value", pg.JSONB(none_as_null=True), nullable=True),
        sa.Column("qualifiers", pg.JSONB(), nullable=False),
        sa.Column("evidence", pg.JSONB(), nullable=False),
        sa.Column("origin", sa.String(24), nullable=False),
        sa.UniqueConstraint("batch_id", "key", "scope_hash", "origin", name="uq_ai_fact_identity"),
        sa.CheckConstraint("scope_hash ~ '^[0-9a-f]{64}$'", name="ck_ai_fact_scope_hash"),
        sa.CheckConstraint("key IN ('pets','smoking','couples','children','tenant_groups','capacity_total',"
                           "'current_room_residents','available_spots','price','deposit','furnished','bills_included',"
                           "'balcony','terrace','amenity','rental_mode','accommodation','geography','availability',"
                           "'minimum_stay','maximum_stay')", name="ck_ai_fact_key"),
        sa.CheckConstraint("status IN ('explicit_allow','explicit_deny','conditional','unknown','conflict',"
                           "'legacy_unverified')", name="ck_ai_fact_status"),
        sa.CheckConstraint("origin IN ('owner_explicit','source_structured','source_text','model_extracted',"
                           "'legacy_default')", name="ck_ai_fact_origin"),
        sa.CheckConstraint("(origin = 'legacy_default') = (status = 'legacy_unverified')", name="ck_ai_fact_legacy"),
        sa.CheckConstraint("(status IN ('unknown','conflict','legacy_unverified') AND typed_value IS NULL) OR "
                           "(status IN ('explicit_allow','explicit_deny') AND typed_value IS NOT NULL) OR "
                           "status = 'conditional'", name="ck_ai_fact_value_status"),
        sa.CheckConstraint("typed_value IS NULL OR (jsonb_typeof(typed_value) = 'object' AND "
                           "octet_length(typed_value::text) <= 4096)", name="ck_ai_fact_value_shape"),
        sa.CheckConstraint("jsonb_typeof(qualifiers) = 'object' AND octet_length(qualifiers::text) <= 2048",
                           name="ck_ai_fact_qualifiers"),
        sa.CheckConstraint("jsonb_typeof(evidence) = 'array' AND jsonb_array_length(evidence) <= 16 AND "
                           "octet_length(evidence::text) <= 65536 AND "
                           "((status IN ('unknown','legacy_unverified') AND jsonb_array_length(evidence) = 0) OR "
                           "(status NOT IN ('unknown','legacy_unverified') AND jsonb_array_length(evidence) > 0))",
                           name="ck_ai_fact_evidence"),
    )
    op.create_table(
        "ai_listing_search_features",
        sa.Column("canonical_listing_id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("feature_revision", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("taxonomy_version", sa.String(32), nullable=False),
        sa.Column("resolver_version", sa.String(64), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("features", pg.JSONB(), nullable=False),
        sa.CheckConstraint("schema_version = 'ai-facts.v1' AND taxonomy_version = 'ai-search.v1'",
                           name="ck_ai_projection_versions"),
        sa.CheckConstraint("feature_revision > 0", name="ck_ai_projection_revision"),
        sa.CheckConstraint("input_hash ~ '^[0-9a-f]{64}$'", name="ck_ai_projection_hash"),
        sa.CheckConstraint("resolver_version ~ '^[a-zA-Z0-9][a-zA-Z0-9._-]*$'", name="ck_ai_projection_resolver"),
        sa.CheckConstraint("jsonb_typeof(features) = 'array' AND jsonb_array_length(features) <= 128 "
                           "AND octet_length(features::text) <= 524288", name="ck_ai_projection_features"),
    )


def downgrade():
    # Preserve provenance/projection history for rollback; old code ignores it.
    pass
