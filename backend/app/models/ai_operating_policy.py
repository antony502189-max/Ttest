"""Separate proof age; never changes the accepted v2 live-input binding."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class AiProofAge(Base):
    __tablename__ = "ai_proof_ages"
    __table_args__ = (CheckConstraint("signature ~ '^[0-9a-f]{64}$'", name="ck_ai_proof_age_signature"),)
    canonical_listing_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    signature: Mapped[str] = mapped_column(String(64))
    prepared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AiErasureBinding(Base):
    __tablename__ = "ai_erasure_bindings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_ai_erasure_binding_singleton"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    journal_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
