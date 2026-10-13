import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import get_settings
from ...db.session import get_session
from ...models import Listing, User
from ...models.commercial_advertisement import CommercialAdvertisement
from ...models.payment_order import PaymentOrder
from ...services.commercial_advertisements import (
    MAX_ACTIVE_HOMEPAGE_ADS,
    PACKAGE_PRICE_CENTS,
    lock_advertising_capacity,
    occupied_slots,
    require_free_slot,
)
from ...services.payment_fulfillment import advertisement_fingerprint, apply_stripe_session
from ...services.stripe_checkout import (
    create_stripe_session,
    expire_stripe_session,
    retrieve_stripe_session,
    verified_stripe_event,
)
from ..dependencies import current_user, require_admin

router = APIRouter(prefix="/payments", tags=["payments"])
logger = logging.getLogger(__name__)
TOP_PACKAGE_PRICES_CENTS = {1: 100, 7: 500, 30: 1000}


class TopCheckoutRequest(BaseModel):
    days: int = Field(ge=1, le=30)


class CheckoutResponse(BaseModel):
    url: str
    amountCents: int
    currency: str = "EUR"


@router.get("/advertisements/{ad_id}/quote")
async def advertisement_quote(
    ad_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
):
    ad = await session.scalar(select(CommercialAdvertisement).where(
        CommercialAdvertisement.id == ad_id, CommercialAdvertisement.owner_user_id == user.id,
    ))
    if not ad:
        raise HTTPException(404, "Advertisement not found")
    legacy = ad.package_id == "test_homepage_30d"
    return {"days": 30 if legacy else 1,
            "amountCents": get_settings().advertisement_30d_price_cents if legacy else PACKAGE_PRICE_CENTS,
            "currency": "EUR", "available": await occupied_slots(session, exclude_id=ad.id) < MAX_ACTIVE_HOMEPAGE_ADS}


async def checkout(
    session: AsyncSession, user: User, kind: str, target_id: UUID, days: int, amount: int,
    name: str, return_path: str, fingerprint: str | None = None,
) -> CheckoutResponse:
    if not get_settings().stripe_secret_key or not get_settings().stripe_webhook_secret:
        raise HTTPException(503, "Stripe is not configured")
    previous = await session.scalar(
        select(PaymentOrder).where(
            PaymentOrder.owner_user_id == user.id,
            PaymentOrder.kind == kind,
            PaymentOrder.target_id == target_id,
            PaymentOrder.status == "pending",
        ).order_by(PaymentOrder.created_at.desc()).limit(1).with_for_update()
    )
    if previous and previous.checkout_url and previous.stripe_session_id:
        remote = await retrieve_stripe_session(previous.stripe_session_id)
        if remote["status"] == "complete":
            if remote.get("payment_status") == "paid":
                await apply_stripe_session(remote, "checkout.session.completed", session)
            raise HTTPException(409, "Payment is awaiting confirmation; do not pay again")
        if remote["status"] == "open":
            if previous.days == days and previous.amount_cents == amount:
                return CheckoutResponse(url=previous.checkout_url, amountCents=amount)
            raise HTTPException(409, "An unfinished payment already exists for this item")
    if previous:
        previous.status = "expired"
    order = PaymentOrder(
        owner_user_id=user.id, kind=kind, target_id=target_id,
        days=days, amount_cents=amount, status="pending", advertisement_fingerprint=fingerprint,
    )
    session.add(order)
    await session.flush()
    order.stripe_session_id, order.checkout_url = await create_stripe_session(order, name, return_path)
    await session.commit()
    return CheckoutResponse(url=order.checkout_url, amountCents=amount)


@router.post("/advertisements/{ad_id}/checkout", response_model=CheckoutResponse)
async def advertisement_checkout(
    ad_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
):
    await lock_advertising_capacity(session)
    ad = await session.scalar(select(CommercialAdvertisement).where(
        CommercialAdvertisement.id == ad_id,
        CommercialAdvertisement.owner_user_id == user.id,
    ).with_for_update())
    if not ad:
        raise HTTPException(404, "Advertisement not found")
    if ad.status != "pending_payment" or ad.payment_status != "unpaid":
        raise HTTPException(409, "Advertisement is not awaiting payment")
    unresolved = await session.scalar(select(PaymentOrder.id).where(
        PaymentOrder.target_id == ad.id, PaymentOrder.owner_user_id == user.id,
        PaymentOrder.kind == "advertisement", PaymentOrder.status == "paid",
        PaymentOrder.fulfillment_status == "review_required",
    ).limit(1))
    if unresolved:
        raise HTTPException(409, "A paid advertisement needs review; do not pay again")
    settings = get_settings()
    legacy = ad.package_id == "test_homepage_30d"
    amount = settings.advertisement_30d_price_cents if legacy else PACKAGE_PRICE_CENTS
    if amount < 50:
        raise HTTPException(503, "Advertisement price has not been configured")
    await require_free_slot(session, exclude_id=ad.id)
    days = 30 if legacy else 1
    return await checkout(session, user, "advertisement", ad.id, days, amount,
                          f"Publicidad 112233.es · {days} {'día' if days == 1 else 'días'}", f"/publicidad/{ad.id}/checkout", advertisement_fingerprint(ad))


@router.post("/listings/{listing_id}/top/checkout", response_model=CheckoutResponse)
async def listing_top_checkout(
    listing_id: UUID, payload: TopCheckoutRequest, user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await lock_advertising_capacity(session)
    listing = await session.scalar(select(Listing).where(
        Listing.id == listing_id, Listing.owner_user_id == user.id,
    ).with_for_update())
    if not listing:
        raise HTTPException(404, "Listing not found")
    if listing.status != "published" or listing.is_external or listing.deleted_at is not None:
        raise HTTPException(409, "Only your published listing can be promoted")
    if payload.days not in TOP_PACKAGE_PRICES_CENTS:
        raise HTTPException(422, "Choose a TOP package of 1, 7 or 30 days")
    return await checkout(session, user, "listing_top", listing.id, payload.days,
                          TOP_PACKAGE_PRICES_CENTS[payload.days],
                          f"TOP 112233.es · {payload.days} {'día' if payload.days == 1 else 'días'}", "/mis-anuncios")


@router.post("/stripe/webhook")
async def stripe_webhook(
    request: Request, stripe_signature: str = Header(default="", alias="Stripe-Signature"),
    session: AsyncSession = Depends(get_session),
):
    event = verified_stripe_event(await request.body(), stripe_signature)
    event_type = event.get("type")
    if event_type not in {"checkout.session.completed", "checkout.session.async_payment_succeeded",
                          "checkout.session.expired"}:
        return {"received": True}
    data = event.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("object"), dict):
        raise HTTPException(400, "Invalid Stripe event")
    checkout_session = data["object"]
    if event_type != "checkout.session.expired" and checkout_session.get("payment_status") != "paid":
        return {"received": True}
    return await apply_stripe_session(checkout_session, event_type, session)


@router.get("/advertisements/{ad_id}/status")
async def advertisement_payment_status(ad_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await lock_advertising_capacity(session)
    ad = await session.scalar(select(CommercialAdvertisement).where(
        CommercialAdvertisement.id == ad_id, CommercialAdvertisement.owner_user_id == user.id,
    ).with_for_update())
    if not ad:
        raise HTTPException(404, "Advertisement not found")
    order = await session.scalar(select(PaymentOrder).where(
        PaymentOrder.target_id == ad.id, PaymentOrder.owner_user_id == user.id, PaymentOrder.kind == "advertisement",
    ).order_by(PaymentOrder.created_at.desc()).limit(1).with_for_update())
    now = datetime.now(UTC)
    if order and order.status == "pending" and (order.last_reconciled_at is None or order.last_reconciled_at < now - timedelta(seconds=10)):
        order.last_reconciled_at = now
        try:
            remote = await retrieve_stripe_session(order.stripe_session_id)
            if remote["status"] == "complete" and remote.get("payment_status") == "paid":
                await apply_stripe_session(remote, "checkout.session.completed", session)
            elif remote["status"] == "expired":
                order.status = "expired"
        except HTTPException:
            logger.warning("advertising_payment_status_temporarily_unavailable")
        await session.commit()
    return {"advertisementId": str(ad.id), "status": ad.status, "paymentStatus": ad.payment_status,
            "orderStatus": order.status if order else None,
            "fulfillmentStatus": order.fulfillment_status if order else None}


@router.post("/advertisements/{ad_id}/checkout/cancel")
async def cancel_advertisement_checkout(ad_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await lock_advertising_capacity(session)
    ad = await session.scalar(select(CommercialAdvertisement).where(
        CommercialAdvertisement.id == ad_id, CommercialAdvertisement.owner_user_id == user.id,
    ).with_for_update())
    if not ad:
        raise HTTPException(404, "Advertisement not found")
    order = await session.scalar(select(PaymentOrder).where(
        PaymentOrder.target_id == ad.id, PaymentOrder.owner_user_id == user.id,
        PaymentOrder.kind == "advertisement", PaymentOrder.status == "pending",
    ).order_by(PaymentOrder.created_at.desc()).limit(1).with_for_update())
    if order:
        remote = await expire_stripe_session(order.stripe_session_id)
        if remote["status"] == "complete" and remote.get("payment_status") == "paid":
            await apply_stripe_session(remote, "checkout.session.completed", session)
            return {"cancelled": False, "paid": True}
        if remote["status"] != "expired":
            raise HTTPException(409, "Payment is awaiting confirmation; do not pay again")
        order.status = "expired"
        await session.commit()
    return {"cancelled": True, "paid": ad.payment_status == "paid"}


@router.get("/admin/review-required")
async def payment_review_queue(user: User = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    orders = (await session.scalars(select(PaymentOrder).where(
        PaymentOrder.status == "paid", PaymentOrder.fulfillment_status == "review_required",
    ).order_by(PaymentOrder.paid_at.desc()).limit(100))).all()
    return [{"id": str(order.id), "kind": order.kind, "targetId": str(order.target_id),
             "amountCents": order.amount_cents, "paidAt": order.paid_at, "note": order.fulfillment_note}
            for order in orders]
