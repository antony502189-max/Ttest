"""Durable fenced scan and minimal match IDs; account/search deletion cascades."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class AiSavedRematch(Base):
    __tablename__ = "ai_saved_rematch"
    __table_args__ = (
        CheckConstraint("fence >= 0", name="ck_ai_saved_rematch_fence"),
        CheckConstraint("(lease_token IS NULL) = (lease_until IS NULL)", name="ck_ai_saved_rematch_lease"),
    )
    saved_search_id: Mapped[UUID] = mapped_column(ForeignKey("ai_saved_searches.saved_search_id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    next_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    cursor_listing_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    fence: Mapped[int] = mapped_column(BigInteger, default=0)
    lease_token: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AiSavedSeen(Base):
    __tablename__ = "ai_saved_seen"
    saved_search_id: Mapped[UUID] = mapped_column(ForeignKey("ai_saved_searches.saved_search_id", ondelete="CASCADE"), primary_key=True)
    listing_id: Mapped[UUID] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
