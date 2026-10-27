from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class AiFactCatalog(Base):
    __tablename__ = "ai_fact_catalogs"
    __table_args__ = (CheckConstraint("revision >= 0", name="ck_ai_catalog_revision"),)
    canonical_listing_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)


class AiFactSource(Base):
    __tablename__ = "ai_fact_sources"
    __table_args__ = (
        CheckConstraint("generation > 0", name="ck_ai_source_generation"),
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$' AND source_fingerprint ~ '^[0-9a-f]{64}$' "
                        "AND snapshot_hash ~ '^[0-9a-f]{64}$'",
                        name="ck_ai_source_hashes"),
        CheckConstraint("source_status IN ('active','unknown','unavailable','retired')", name="ck_ai_source_status"),
        CheckConstraint("schema_version = 'ai-facts.v1' AND taxonomy_version = 'ai-search.v1'", name="ck_ai_source_versions"),
        CheckConstraint("extractor_version ~ '^[a-zA-Z0-9][a-zA-Z0-9._-]*$'", name="ck_ai_source_extractor"),
        Index("ix_ai_source_canonical", "canonical_listing_id"),
    )
    source_record_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    canonical_listing_id: Mapped[UUID] = mapped_column(ForeignKey("ai_fact_catalogs.canonical_listing_id"))
    generation: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    source_fingerprint: Mapped[str] = mapped_column(String(64))
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    source_status: Mapped[str] = mapped_column(String(16))
    schema_version: Mapped[str] = mapped_column(String(32))
    taxonomy_version: Mapped[str] = mapped_column(String(32))
    extractor_version: Mapped[str] = mapped_column(String(64))
    batch_id: Mapped[UUID | None] = mapped_column(ForeignKey("ai_listing_fact_batches.id"))


class AiFactJob(Base):
    __tablename__ = "ai_fact_jobs"
    __table_args__ = (
        UniqueConstraint("source_record_id", "generation", name="uq_ai_job_generation"),
        CheckConstraint("generation > 0 AND fence >= 0 AND attempts >= 0", name="ck_ai_job_counters"),
        CheckConstraint("status IN ('pending','running','succeeded','failed','superseded')", name="ck_ai_job_status"),
        CheckConstraint("(status = 'running') = (lease_until IS NOT NULL)", name="ck_ai_job_lease"),
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$' AND snapshot_hash ~ '^[0-9a-f]{64}$'", name="ck_ai_job_hash"),
        CheckConstraint("schema_version = 'ai-facts.v1' AND taxonomy_version = 'ai-search.v1'", name="ck_ai_job_versions"),
        CheckConstraint("extractor_version ~ '^[a-zA-Z0-9][a-zA-Z0-9._-]*$'", name="ck_ai_job_extractor"),
        CheckConstraint("(status = 'succeeded' AND result_revision IS NOT NULL AND result_hash IS NOT NULL) OR "
                        "(status <> 'succeeded' AND result_revision IS NULL AND result_hash IS NULL)",
                        name="ck_ai_job_result"),
        CheckConstraint("result_revision IS NULL OR result_revision > 0", name="ck_ai_job_revision"),
        CheckConstraint("result_hash IS NULL OR result_hash ~ '^[0-9a-f]{64}$'", name="ck_ai_job_result_hash"),
        CheckConstraint("failure_code IS NULL OR failure_code IN ('EXTRACTOR_FAILED','INVALID_RESULT','ATTEMPTS_EXHAUSTED')",
                        name="ck_ai_job_failure"),
        Index("ix_ai_job_claim", "available_at", "id", postgresql_where=text("status IN ('pending','running')")),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    source_record_id: Mapped[UUID] = mapped_column(ForeignKey("ai_fact_sources.source_record_id"))
    canonical_listing_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    generation: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[str] = mapped_column(String(32))
    taxonomy_version: Mapped[str] = mapped_column(String(32))
    extractor_version: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    fence: Mapped[int] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    result_revision: Mapped[int | None] = mapped_column(Integer)
    result_hash: Mapped[str | None] = mapped_column(String(64))
    failure_code: Mapped[str | None] = mapped_column(String(32))


class AiFactRematchEvent(Base):
    """Durable signal only; no notification delivery or outbox consumer yet."""

    __tablename__ = "ai_fact_rematch_events"
    __table_args__ = (
        UniqueConstraint("canonical_listing_id", "feature_revision", name="uq_ai_rematch_revision"),
        CheckConstraint("feature_revision > 0", name="ck_ai_rematch_revision"),
        CheckConstraint("input_hash ~ '^[0-9a-f]{64}$'", name="ck_ai_rematch_hash"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    canonical_listing_id: Mapped[UUID] = mapped_column(ForeignKey("ai_fact_catalogs.canonical_listing_id"))
    feature_revision: Mapped[int] = mapped_column(Integer)
    input_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
