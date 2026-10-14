from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class PaymentOrder(Base):
    __tablename__ = "payment_orders"
    __table_args__ = (
        CheckConstraint("kind IN ('advertisement','listing_top','homepage_hero')", name="ck_payment_order_kind"),
        CheckConstraint("status IN ('pending','paid','expired')", name="ck_payment_order_status"),
        CheckConstraint("amount_cents > 0", name="ck_payment_order_amount"),
        CheckConstraint("fulfillment_status IN ('pending','fulfilled','review_required')", name="ck_payment_order_fulfillment"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(24))
    target_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    days: Mapped[int] = mapped_column(Integer)
    amount_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    stripe_session_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    checkout_url: Mapped[str | None] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fulfillment_status: Mapped[str] = mapped_column(String(24), default="pending", server_default="pending")
    fulfillment_note: Mapped[str | None] = mapped_column(Text)
    advertisement_fingerprint: Mapped[str | None] = mapped_column(String(64))
