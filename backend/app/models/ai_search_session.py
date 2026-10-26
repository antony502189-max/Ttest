"""Structured conversation state and durable operation receipts, never transcripts."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class AISearchSession(Base):
    __tablename__ = "ai_search_sessions"
    __table_args__ = (
        CheckConstraint("subject_kind IN ('guest', 'auth')", name="ck_ai_session_subject"),
        CheckConstraint("version >= 0", name="ck_ai_session_version"),
        CheckConstraint(
            "jsonb_typeof(criteria) = 'object' AND octet_length(criteria::text) <= 65536", name="ck_ai_session_criteria"
        ),
        Index("ix_ai_session_owner", "subject_kind", "subject_id"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    subject_kind: Mapped[str] = mapped_column(String(5))
    subject_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    schema_version: Mapped[str] = mapped_column(String(32))
    taxonomy_version: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer, server_default="0")
    criteria: Mapped[dict] = mapped_column(JSONB)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AISearchResult(Base):
    __tablename__ = "ai_search_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["subject_kind", "subject_id", "idempotency_key"],
            ["ai_search_requests.subject_kind", "ai_search_requests.subject_id", "ai_search_requests.idempotency_key"],
            name="fk_ai_result_operation",
        ),
        UniqueConstraint("subject_kind", "subject_id", "idempotency_key", name="uq_ai_result_operation"),
        CheckConstraint("session_version > 0 AND result_count >= 0", name="ck_ai_result_counts"),
        CheckConstraint(
            "jsonb_typeof(intent) = 'object' AND octet_length(intent::text) <= 65536", name="ck_ai_result_intent"
        ),
        CheckConstraint("intent_hash ~ '^[0-9a-f]{64}$'", name="ck_ai_result_hash"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    subject_kind: Mapped[str] = mapped_column(String(5))
    subject_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    idempotency_key: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    session_id: Mapped[UUID] = mapped_column(ForeignKey("ai_search_sessions.id"))
    session_version: Mapped[int] = mapped_column(Integer)
    intent: Mapped[dict] = mapped_column(JSONB)
    intent_hash: Mapped[str] = mapped_column(String(64))
    result_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
