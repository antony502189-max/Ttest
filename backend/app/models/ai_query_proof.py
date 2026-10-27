"""Disposable verification cache; no FK or mutation of legacy catalog."""
from uuid import UUID

from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class AiQueryProof(Base):
    __tablename__ = "ai_query_proofs"
    __table_args__ = (
        CheckConstraint("signature ~ '^[0-9a-f]{64}$' AND vocabulary_hash ~ '^[0-9a-f]{64}$'", name="ck_ai_query_proof_hashes"),
        CheckConstraint("feature_revision > 0", name="ck_ai_query_proof_revision"),
        CheckConstraint("resolver_version ~ '^[a-zA-Z0-9][a-zA-Z0-9._-]*$'", name="ck_ai_query_proof_resolver"),
    )
    canonical_listing_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    signature: Mapped[str] = mapped_column(String(64))
    vocabulary_hash: Mapped[str] = mapped_column(String(64))
    resolver_version: Mapped[str] = mapped_column(String(64))
    feature_revision: Mapped[int] = mapped_column(Integer)
