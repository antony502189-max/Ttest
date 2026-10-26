"""Inert AI-03 storage. Existing catalog tables and deletion paths are untouched."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, column, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class AiListingFactBatch(Base):
    __tablename__ = "ai_listing_fact_batches"
    __table_args__ = (
        CheckConstraint("schema_version = 'ai-facts.v1' AND taxonomy_version = 'ai-search.v1'", name="ck_ai_batch_versions"),
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="ck_ai_batch_hash"),
        CheckConstraint("source_generation > 0", name="ck_ai_batch_generation"),
        CheckConstraint("extractor_version ~ '^[a-zA-Z0-9][a-zA-Z0-9._-]*$'", name="ck_ai_batch_extractor"),
        CheckConstraint("source_status IN ('active','unknown','unavailable','retired')", name="ck_ai_batch_status"),
        CheckConstraint("last_successful_check_at <= observed_at AND last_content_change_at <= observed_at "
                        "AND last_check_error_at <= observed_at", name="ck_ai_batch_timestamps"),
        Index("ix_ai_batch_listing", "canonical_listing_id"),
        Index("ix_ai_batch_source_generation", "source_record_id", "source_generation"),
        Index("uq_ai_batch_identity", "canonical_listing_id",
              column("source_record_id").is_(None).self_group(),
              func.coalesce(column("source_record_id"), column("canonical_listing_id")),
              "source_generation", "content_hash", "extractor_version", "schema_version", "taxonomy_version",
              unique=True),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    # No new FKs into legacy tables: deletion/import behavior must not change.
    # AI-04 validates these references and current source identity under locks.
    canonical_listing_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    source_record_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    source_generation: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[str] = mapped_column(String(32))
    taxonomy_version: Mapped[str] = mapped_column(String(32))
    extractor_version: Mapped[str] = mapped_column(String(64))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_status: Mapped[str] = mapped_column(String(16))
    last_successful_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_content_change_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_check_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AiListingFact(Base):
    __tablename__ = "ai_listing_facts"
    __table_args__ = (
        UniqueConstraint("batch_id", "key", "scope_hash", "origin", name="uq_ai_fact_identity"),
        CheckConstraint("scope_hash ~ '^[0-9a-f]{64}$'", name="ck_ai_fact_scope_hash"),
        CheckConstraint("key IN ('pets','smoking','couples','children','tenant_groups','capacity_total',"
                        "'current_room_residents','available_spots','price','deposit','furnished','bills_included',"
                        "'balcony','terrace','amenity','rental_mode','accommodation','geography','availability',"
                        "'minimum_stay','maximum_stay')", name="ck_ai_fact_key"),
        CheckConstraint("status IN ('explicit_allow','explicit_deny','conditional','unknown','conflict',"
                        "'legacy_unverified')", name="ck_ai_fact_status"),
        CheckConstraint("origin IN ('owner_explicit','source_structured','source_text','model_extracted',"
                        "'legacy_default')", name="ck_ai_fact_origin"),
        CheckConstraint("(origin = 'legacy_default') = (status = 'legacy_unverified')", name="ck_ai_fact_legacy"),
        CheckConstraint("(status IN ('unknown','conflict','legacy_unverified') AND typed_value IS NULL) OR "
                        "(status IN ('explicit_allow','explicit_deny') AND typed_value IS NOT NULL) OR "
                        "status = 'conditional'", name="ck_ai_fact_value_status"),
        CheckConstraint("typed_value IS NULL OR (jsonb_typeof(typed_value) = 'object' AND "
                        "octet_length(typed_value::text) <= 4096)", name="ck_ai_fact_value_shape"),
        CheckConstraint("jsonb_typeof(qualifiers) = 'object' AND octet_length(qualifiers::text) <= 2048",
                        name="ck_ai_fact_qualifiers"),
        CheckConstraint("jsonb_typeof(evidence) = 'array' AND jsonb_array_length(evidence) <= 16 AND "
                        "octet_length(evidence::text) <= 65536 AND "
                        "((status IN ('unknown','legacy_unverified') AND jsonb_array_length(evidence) = 0) OR "
                        "(status NOT IN ('unknown','legacy_unverified') AND jsonb_array_length(evidence) > 0))",
                        name="ck_ai_fact_evidence"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    batch_id: Mapped[UUID] = mapped_column(ForeignKey("ai_listing_fact_batches.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(32))
    scope_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24))
    typed_value: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    qualifiers: Mapped[dict] = mapped_column(JSONB)
    evidence: Mapped[list] = mapped_column(JSONB)
    origin: Mapped[str] = mapped_column(String(24))


class AiListingSearchFeatures(Base):
    __tablename__ = "ai_listing_search_features"
    __table_args__ = (
        CheckConstraint("schema_version = 'ai-facts.v1' AND taxonomy_version = 'ai-search.v1'",
                        name="ck_ai_projection_versions"),
        CheckConstraint("feature_revision > 0", name="ck_ai_projection_revision"),
        CheckConstraint("input_hash ~ '^[0-9a-f]{64}$'", name="ck_ai_projection_hash"),
        CheckConstraint("resolver_version ~ '^[a-zA-Z0-9][a-zA-Z0-9._-]*$'", name="ck_ai_projection_resolver"),
        CheckConstraint("jsonb_typeof(features) = 'array' AND jsonb_array_length(features) <= 128 "
                        "AND octet_length(features::text) <= 524288", name="ck_ai_projection_features"),
    )
    canonical_listing_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    feature_revision: Mapped[int] = mapped_column(Integer)
    schema_version: Mapped[str] = mapped_column(String(32))
    taxonomy_version: Mapped[str] = mapped_column(String(32))
    resolver_version: Mapped[str] = mapped_column(String(64))
    input_hash: Mapped[str] = mapped_column(String(64))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    features: Mapped[list] = mapped_column(JSONB)
