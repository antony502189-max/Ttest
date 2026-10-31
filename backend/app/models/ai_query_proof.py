"""Disposable verification cache; no FK or mutation of legacy catalog."""
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class AiQueryProof(Base):
    __tablename__ = "ai_query_proofs"
    __table_args__ = (
        CheckConstraint("signature ~ '^[0-9a-f]{64}$' AND vocabulary_hash ~ '^[0-9a-f]{64}$'", name="ck_ai_query_proof_hashes"),
        CheckConstraint("feature_revision > 0", name="ck_ai_query_proof_revision"),
        CheckConstraint("resolver_version ~ '^[a-zA-Z0-9][a-zA-Z0-9._-]*$'", name="ck_ai_query_proof_resolver"),
        CheckConstraint("(input_signature IS NULL AND input_binding IS NULL AND input_vector IS NULL) OR "
                        "(input_signature IS NOT NULL AND input_binding IS NOT NULL AND input_vector IS NOT NULL AND "
                        "input_signature ~ '^[0-9a-f]{64}$' AND input_binding ~ '^[0-9a-f]{64}$')",
                        name="ck_ai_query_proof_inputs"),
        CheckConstraint("input_status IN ('legacy','current','changed','missing')", name="ck_ai_query_proof_input_status"),
        ForeignKeyConstraint(["match_cohort_id"], ["ai_live_match_cohorts.id"], name="fk_ai_proof_cohort",
                             onupdate="CASCADE", ondelete="SET NULL"),
        Index("ix_ai_proof_live_read", "canonical_listing_id", postgresql_include=[
            "resolver_version", "vocabulary_hash", "signature", "input_status", "input_contract", "input_epoch", "input_schema", "match_cohort_id"]),
    )
    canonical_listing_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    signature: Mapped[str] = mapped_column(String(64))
    vocabulary_hash: Mapped[str] = mapped_column(String(64))
    resolver_version: Mapped[str] = mapped_column(String(64))
    feature_revision: Mapped[int] = mapped_column(Integer)
    input_signature: Mapped[str | None] = mapped_column(String(64))
    input_binding: Mapped[str | None] = mapped_column(String(64))
    input_vector: Mapped[dict | None] = mapped_column(JSONB)
    input_status: Mapped[str] = mapped_column(String(16), server_default="legacy")
    input_contract: Mapped[str | None] = mapped_column(String(64))
    input_epoch: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    input_schema: Mapped[str | None] = mapped_column(String(64))
    match_cohort_id: Mapped[str | None] = mapped_column(String(64))


class AiLiveMatchCohort(Base):
    __tablename__ = "ai_live_match_cohorts"
    __table_args__ = (CheckConstraint("id ~ '^[0-9a-f]{64}$' AND id=encode(sha256(convert_to(features::text,'UTF8')),'hex') "
        "AND jsonb_typeof(features)='array' AND jsonb_array_length(features)<=128", name="ck_ai_live_cohort_identity"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    features: Mapped[list] = mapped_column(JSONB)


class AiLiveInputEpoch(Base):
    __tablename__ = "ai_live_input_epochs"
    __table_args__ = (CheckConstraint("id = 1", name="ck_ai_live_epoch_singleton"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    epoch: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), server_default=text("gen_random_uuid()"))


class AiLiveInputVersion(Base):
    __tablename__ = "ai_live_input_versions"
    __table_args__ = (CheckConstraint("kind IN ('listing','external','batch')", name="ck_ai_live_input_kind"),
                     UniqueConstraint("kind", "record_id", "token", name="uq_ai_live_input_reference"))
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    record_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    token: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), server_default=text("gen_random_uuid()"))


class AiLiveProofDependency(Base):
    __tablename__ = "ai_live_proof_dependencies"
    __table_args__ = (
        ForeignKeyConstraint(["proof_listing_id"], ["ai_query_proofs.canonical_listing_id"],
                             name="fk_ai_live_dep_proof", onupdate="CASCADE", ondelete="CASCADE"),
        ForeignKeyConstraint(["kind", "record_id", "token"],
                             ["ai_live_input_versions.kind", "ai_live_input_versions.record_id", "ai_live_input_versions.token"],
                             name="fk_ai_live_dep_version", onupdate="CASCADE", ondelete="CASCADE"),
        Index("ix_ai_live_dependency_input", "kind", "record_id", "token"),
    )
    proof_listing_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    record_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    token: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))


class AiProofPopulation(Base):
    __tablename__ = "ai_proof_population"
    __table_args__ = (CheckConstraint("id = 1 AND revision > 0", name="ck_ai_proof_population_singleton"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    epoch: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), server_default=text("gen_random_uuid()"))
    revision: Mapped[int] = mapped_column(BigInteger)
