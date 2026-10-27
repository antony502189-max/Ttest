"""Authoritative AI usage ledger; no raw user text, audio or provider payloads."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class AIUsageDay(Base):
    __tablename__ = "ai_usage_days"
    __table_args__ = (
        CheckConstraint("subject_kind IN ('guest', 'auth')", name="ck_ai_usage_subject_kind"),
        CheckConstraint("used >= 0 AND reserved >= 0 AND used + reserved <= quota_limit", name="ck_ai_usage_bounds"),
    )
    subject_kind: Mapped[str] = mapped_column(String(5), primary_key=True)
    subject_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    madrid_date: Mapped[date] = mapped_column(Date, primary_key=True)
    quota_limit: Mapped[int] = mapped_column(
        Integer,
        Computed("CASE subject_kind WHEN 'guest' THEN 3 ELSE 200 END", persisted=True),
    )
    used: Mapped[int] = mapped_column(Integer, server_default="0")
    reserved: Mapped[int] = mapped_column(Integer, server_default="0")


class AISearchRequest(Base):
    __tablename__ = "ai_search_requests"
    __table_args__ = (
        ForeignKeyConstraint(
            ["subject_kind", "subject_id", "madrid_date"],
            ["ai_usage_days.subject_kind", "ai_usage_days.subject_id", "ai_usage_days.madrid_date"],
            name="fk_ai_request_day",
        ),
        CheckConstraint("request_hash ~ '^[0-9a-f]{64}$'", name="ck_ai_request_hash"),
        CheckConstraint("channel IN ('text', 'voice')", name="ck_ai_request_channel"),
        CheckConstraint("expected_session_version >= 0 AND fence >= 0", name="ck_ai_request_versions"),
        CheckConstraint("status IN ('reserved', 'running', 'succeeded', 'failed')", name="ck_ai_request_status"),
        CheckConstraint("recover_after >= lease_until", name="ck_ai_request_recovery"),
        CheckConstraint(
            "((status = 'succeeded') = (result_ref IS NOT NULL)) AND "
            "((status = 'succeeded') = (result_count IS NOT NULL)) AND "
            "(result_count IS NULL OR result_count >= 0)",
            name="ck_ai_request_result",
        ),
        CheckConstraint("(status = 'failed') = (failure_code IS NOT NULL)", name="ck_ai_request_failure"),
        Index("ix_ai_request_recovery", "recover_after", postgresql_where=text("status IN ('reserved', 'running')")),
    )
    subject_kind: Mapped[str] = mapped_column(String(5), primary_key=True)
    subject_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    idempotency_key: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    madrid_date: Mapped[date] = mapped_column(Date)
    channel: Mapped[str] = mapped_column(String(5))
    session_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    expected_session_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(9))
    fence: Mapped[int] = mapped_column(BigInteger, server_default="0")
    lease_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recover_after: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_ref: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    result_count: Mapped[int | None] = mapped_column(Integer)
    failure_code: Mapped[str | None] = mapped_column(String(40))
