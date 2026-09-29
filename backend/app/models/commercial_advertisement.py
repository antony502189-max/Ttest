from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class CommercialAdvertisement(Base):
    __tablename__ = "commercial_advertisements"
    __table_args__ = (
        CheckConstraint("status IN ('pending_payment','pending_review','active','rejected','cancelled')", name="ck_commercial_ad_status"),
        CheckConstraint("payment_status IN ('unpaid','pending','paid','failed','refunded')", name="ck_commercial_ad_payment"),
        CheckConstraint("destination_type IN ('website','phone','whatsapp','email')", name="ck_commercial_ad_destination"),
        Index("ix_commercial_ad_homepage", "placement", "status", "payment_status", "admin_priority"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    image_asset_id: Mapped[UUID] = mapped_column(ForeignKey("media_assets.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = mapped_column(String(90))
    description: Mapped[str] = mapped_column(String(300))
    destination_type: Mapped[str] = mapped_column(String(16))
    destination: Mapped[str] = mapped_column(String(2048))
    placement: Mapped[str] = mapped_column(String(40), default="homepage_bottom")
    status: Mapped[str] = mapped_column(String(24), default="pending_payment")
    payment_status: Mapped[str] = mapped_column(String(16), default="unpaid")
    package_id: Mapped[str] = mapped_column(String(40), default="test_homepage_30d")
    admin_priority: Mapped[int] = mapped_column(Integer, default=0)
    moderation_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
