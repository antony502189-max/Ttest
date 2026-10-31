"""Disposable verification cache; no FK or mutation of legacy catalog."""
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, Integer, String, text
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
    )
    canonical_listing_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    signature: Mapped[str] = mapped_column(String(64))
    vocabulary_hash: Mapped[str] = mapped_column(String(64))
    resolver_version: Mapped[str] = mapped_column(String(64))
    feature_revision: Mapped[int] = mapped_column(Integer)
    input_signature: Mapped[str | None] = mapped_column(String(64))
    input_binding: Mapped[str | None] = mapped_column(String(64))
    input_vector: Mapped[dict | None] = mapped_column(JSONB)


class AiLiveInputEpoch(Base):
    __tablename__ = "ai_live_input_epochs"
    __table_args__ = (CheckConstraint("id = 1", name="ck_ai_live_epoch_singleton"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    epoch: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), server_default=text("gen_random_uuid()"))


class AiLiveInputVersion(Base):
    __tablename__ = "ai_live_input_versions"
    __table_args__ = (CheckConstraint("kind IN ('listing','external','batch')", name="ck_ai_live_input_kind"),)
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    record_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    token: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), server_default=text("gen_random_uuid()"))


class AiProofPopulation(Base):
    __tablename__ = "ai_proof_population"
    __table_args__ = (CheckConstraint("id = 1 AND revision > 0", name="ck_ai_proof_population_singleton"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    epoch: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), server_default=text("gen_random_uuid()"))
    revision: Mapped[int] = mapped_column(BigInteger)
