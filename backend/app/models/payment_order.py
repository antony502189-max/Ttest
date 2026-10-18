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
        CheckConstraint("status IN ('creating','pending','paid','expired','failed')", name="ck_payment_order_status"),
        CheckConstraint("amount_cents > 0", name="ck_payment_order_amount"),
        CheckConstraint("fulfillment_status IN ('pending','fulfilled','review_required','revoked')", name="ck_payment_order_fulfillment"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(24))
    target_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    days: Mapped[int] = mapped_column(Integer)
    top_municipality_code: Mapped[str | None] = mapped_column(String(5), index=True)
    duration_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
    checkout_name: Mapped[str | None] = mapped_column(String(240))
    return_path: Mapped[str | None] = mapped_column(String(512))
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    stripe_charge_id: Mapped[str | None] = mapped_column(String(255), index=True)
    financial_status: Mapped[str] = mapped_column(String(24), default="normal", server_default="normal")
    refunded_amount_cents: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    dispute_status: Mapped[str | None] = mapped_column(String(48))
    refund_id: Mapped[str | None] = mapped_column(String(255))
    refund_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resolution_reason: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    service_starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    service_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused_ad_status: Mapped[str | None] = mapped_column(String(24))
    refund_attempt: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
