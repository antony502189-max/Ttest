"""Moderation pauses paid TOP for review without reselling its reserved period."""
from datetime import UTC, datetime

from sqlalchemy import select

from ..models.payment_order import PaymentOrder


async def review_paid_top(session, *, reason, listing_id=None, owner_id=None):
    """Caller holds advertising capacity before any User/Listing row locks.

    Keep the promotion, municipality and original service history. Operators
    decide refund/restoration; moderation never silently extends a paid period.
    """
    from .payment_fulfillment import notify_payment
    query = select(PaymentOrder).where(
        PaymentOrder.kind == "listing_top", PaymentOrder.status == "paid",
        PaymentOrder.fulfillment_status == "fulfilled", PaymentOrder.financial_status == "normal",
        (PaymentOrder.service_ends_at.is_(None)) | (PaymentOrder.service_ends_at > datetime.now(UTC)),
    )
    query = query.where(PaymentOrder.target_id == listing_id) if listing_id is not None else query.where(PaymentOrder.owner_user_id == owner_id)
    for order in (await session.scalars(query.with_for_update())).all():
        order.fulfillment_status = "review_required"
        order.fulfillment_note = reason
        await notify_payment(session, order, "payment_review_required", "Tu pago necesita una revisión",
                             "El anuncio no está disponible. Revisaremos el TOP pagado; no vuelvas a pagar.")
