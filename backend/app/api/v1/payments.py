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
from ...models.moderation import ListingPromotion
from ...models.payment_order import PaymentOrder
from ...services.stripe_checkout import create_stripe_session, verified_stripe_event
from ..dependencies import current_user

router = APIRouter(prefix="/payments", tags=["payments"])
logger = logging.getLogger(__name__)
TOP_PACKAGE_PRICES_CENTS = {1: 100, 7: 500, 30: 1000}


class TopCheckoutRequest(BaseModel):
    days: int = Field(ge=1, le=30)


class CheckoutResponse(BaseModel):
    url: str
    amountCents: int
    currency: str = "EUR"


async def checkout(
    session: AsyncSession, user: User, kind: str, target_id: UUID, days: int, amount: int,
    name: str, return_path: str,
) -> CheckoutResponse:
    if not get_settings().stripe_secret_key or not get_settings().stripe_webhook_secret:
        raise HTTPException(503, "Stripe is not configured")
    now = datetime.now(UTC)
    previous = await session.scalar(
        select(PaymentOrder).where(
            PaymentOrder.owner_user_id == user.id,
            PaymentOrder.kind == kind,
            PaymentOrder.target_id == target_id,
            PaymentOrder.status == "pending",
        ).order_by(PaymentOrder.created_at.desc()).limit(1).with_for_update()
    )
    if previous and previous.checkout_url and previous.created_at > now - timedelta(hours=25):
        if previous.days == days and previous.amount_cents == amount:
            return CheckoutResponse(url=previous.checkout_url, amountCents=amount)
        raise HTTPException(409, "An unfinished payment already exists for this item")
    if previous:
        previous.status = "expired"
    order = PaymentOrder(
        owner_user_id=user.id, kind=kind, target_id=target_id,
        days=days, amount_cents=amount, status="pending",
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
    ad = await session.scalar(select(CommercialAdvertisement).where(
        CommercialAdvertisement.id == ad_id,
        CommercialAdvertisement.owner_user_id == user.id,
    ).with_for_update())
    if not ad:
        raise HTTPException(404, "Advertisement not found")
    if ad.status != "pending_payment" or ad.payment_status != "unpaid":
        raise HTTPException(409, "Advertisement is not awaiting payment")
    settings = get_settings()
    amount = settings.advertisement_30d_price_cents
    if amount < 50:
        raise HTTPException(503, "Advertisement price has not been configured")
    return await checkout(session, user, "advertisement", ad.id, 30, amount,
                          "Publicidad 112233.es · 30 días", f"/publicidad/{ad.id}/checkout")


@router.post("/listings/{listing_id}/top/checkout", response_model=CheckoutResponse)
async def listing_top_checkout(
    listing_id: UUID, payload: TopCheckoutRequest, user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
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
                          f"TOP 112233.es · {payload.days} días", "/mis-anuncios")


@router.post("/stripe/webhook")
async def stripe_webhook(
    request: Request, stripe_signature: str = Header(default="", alias="Stripe-Signature"),
    session: AsyncSession = Depends(get_session),
):
    event = verified_stripe_event(await request.body(), stripe_signature)
    if event.get("type") not in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
        return {"received": True}
    checkout_session = event.get("data", {}).get("object", {})
    if checkout_session.get("payment_status") != "paid":
        return {"received": True}
    order_id = checkout_session.get("client_reference_id")
    try:
        order_uuid = UUID(order_id)
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(400, "Unknown payment order") from None
    order = await session.scalar(select(PaymentOrder).where(PaymentOrder.id == order_uuid).with_for_update())
    if not order or order.stripe_session_id != checkout_session.get("id"):
        raise HTTPException(400, "Unknown payment order")
    expected_live = get_settings().stripe_secret_key.startswith("sk_live_")
    if (checkout_session.get("amount_total") != order.amount_cents
            or checkout_session.get("currency") != "eur"
            or checkout_session.get("livemode") is not expected_live):
        raise HTTPException(400, "Payment does not match order")
    if order.status == "paid":
        return {"received": True}
    if order.status == "expired":
        logger.error("stripe_paid_expired_order order_id=%s", order.id)
        order.status = "paid"
        order.paid_at = datetime.now(UTC)
        await session.commit()
        return {"received": True}
    order.status = "paid"
    order.paid_at = datetime.now(UTC)
    if order.kind == "advertisement":
        ad = await session.scalar(select(CommercialAdvertisement).where(
            CommercialAdvertisement.id == order.target_id,
            CommercialAdvertisement.owner_user_id == order.owner_user_id,
        ).with_for_update())
        if ad and ad.status == "pending_payment" and ad.payment_status == "unpaid":
            ad.payment_status = "paid"
            ad.status = "pending_review"
            ad.submitted_at = order.paid_at
        else:
            logger.error("stripe_paid_ad_requires_review order_id=%s", order.id)
    else:
        listing = await session.scalar(select(Listing).where(
            Listing.id == order.target_id,
            Listing.owner_user_id == order.owner_user_id,
        ).with_for_update())
        if listing and listing.status == "published" and not listing.is_external and listing.deleted_at is None:
            promotion = await session.scalar(select(ListingPromotion).where(
                ListingPromotion.listing_id == listing.id,
            ).with_for_update())
            start = max(order.paid_at, promotion.ends_at) if promotion and promotion.ends_at else order.paid_at
            if promotion and promotion.ends_at is None:
                logger.error("stripe_paid_legacy_top_requires_review order_id=%s", order.id)
            elif promotion:
                if promotion.ends_at <= order.paid_at:
                    promotion.starts_at = order.paid_at
                promotion.ends_at = start + timedelta(days=order.days)
                promotion.daily_price_cents = None
                promotion.total_price_cents = (promotion.total_price_cents or 0) + order.amount_cents
            else:
                session.add(ListingPromotion(
                    listing_id=listing.id, boosted_at=order.paid_at, boosted_by=None,
                    starts_at=order.paid_at, ends_at=order.paid_at + timedelta(days=order.days),
                    daily_price_cents=order.amount_cents if order.days == 1 else None,
                ))
        else:
            logger.error("stripe_paid_top_requires_review order_id=%s", order.id)
    await session.commit()
    return {"received": True}
