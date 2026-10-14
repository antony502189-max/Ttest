from datetime import UTC, datetime, timedelta
from fastapi import HTTPException
from sqlalchemy import select
from ..models.payment_order import PaymentOrder
from .commercial_advertisements import lock_advertising_capacity
from .stripe_checkout import create_stripe_session, retrieve_stripe_session, stripe_object


async def finish_creation(order, session, *, create=create_stripe_session):
    """The reservation is committed BEFORE any external IO; retries keep its UUID."""
    if order.created_at and order.created_at < datetime.now(UTC) - timedelta(hours=23):
        order.fulfillment_status = "review_required"
        order.fulfillment_note = "Checkout creation result unknown beyond Stripe idempotency retention; reconcile session manually."
        await session.commit()
        raise HTTPException(409, "Payment creation needs review; do not pay again")
    order_id, name, path = order.id, order.checkout_name, order.return_path
    await session.commit()
    stripe_id, url = await create(order, name, path)
    await lock_advertising_capacity(session)
    fresh = await session.scalar(select(PaymentOrder).where(PaymentOrder.id == order_id).with_for_update().execution_options(populate_existing=True))
    if fresh.stripe_session_id and fresh.stripe_session_id != stripe_id:
        raise HTTPException(409, "Payment creation needs review; do not pay again")
    fresh.stripe_session_id, fresh.checkout_url = stripe_id, url
    if fresh.status == "creating":
        fresh.status = "pending"
    await session.commit()
    return url


async def reconcile_order(order, session, *, retrieve=retrieve_stripe_session, create=create_stripe_session):
    from .payment_fulfillment import apply_stripe_session
    if order.status == "creating" and not order.stripe_session_id:
        await finish_creation(order, session, create=create)
    stripe_id = order.stripe_session_id
    await session.commit()
    if not stripe_id:
        return
    remote = await retrieve(stripe_id)
    if remote["status"] == "expired":
        await apply_stripe_session(remote, "checkout.session.expired", session)
    elif remote["status"] == "complete" and remote.get("payment_status") == "paid":
        await apply_stripe_session(remote, "checkout.session.completed", session)
    elif remote["status"] == "complete" and remote.get("payment_intent"):
        intent = await stripe_object("payment_intents/" + remote["payment_intent"])
        if intent.get("status") in {"requires_payment_method", "canceled"}:
            await apply_stripe_session(remote, "checkout.session.async_payment_failed", session)
