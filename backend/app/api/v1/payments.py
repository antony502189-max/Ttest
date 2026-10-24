import logging
from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import get_settings
from ...db.session import get_session
from ...models import Listing, User
from ...models.commercial_advertisement import CommercialAdvertisement
from ...models.moderation import HomepageHeroPromotion, ListingPromotion
from ...models.payment_order import PaymentOrder
from ...services.commercial_advertisements import (
    MAX_ACTIVE_HOMEPAGE_ADS,
    PACKAGE_PRICE_CENTS,
    PREMIUM_PACKAGE_ID,
    price_for_package,
    capacity_for_placement,
    lock_advertising_capacity,
    occupied_slots,
    require_free_slot,
)
from ...services.homepage_purchase import eligible, slot_available
from ...services.payment_fulfillment import advertisement_fingerprint, apply_stripe_session
from ...services.payment_sessions import finish_creation, reconcile_order
from ...services.promotion_offers import PromotionHours, amount_cents, offers
from ...services.province_top import require_province_top_slot, top_availability
from ...services.stripe_checkout import (
    create_stripe_session,
    expire_stripe_session,
    require_checkout_enabled,
    retrieve_stripe_session,
    verified_stripe_event,
)
from ..dependencies import current_user, require_admin

router = APIRouter(prefix="/payments", tags=["payments"])
logger = logging.getLogger(__name__)
class TopCheckoutRequest(BaseModel):
    durationHours: PromotionHours


class HomepageCheckoutRequest(BaseModel):
    durationHours: PromotionHours


class BannerCheckoutRequest(BaseModel):
    days: int = Field(default=30, ge=30, le=30, strict=True)


class CheckoutResponse(BaseModel):
    url: str
    amountCents: int
    currency: str = "EUR"


@router.get("/advertisements/{ad_id}/quote")
async def advertisement_quote(
    ad_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
    days: int = Query(default=30, ge=30, le=30),
):
    ad = await session.scalar(select(CommercialAdvertisement).where(
        CommercialAdvertisement.id == ad_id, CommercialAdvertisement.owner_user_id == user.id,
    ))
    if not ad:
        raise HTTPException(404, "Advertisement not found")
    reserved_days = await session.scalar(select(PaymentOrder.days).where(
        PaymentOrder.kind == "advertisement", PaymentOrder.target_id == ad.id,
        PaymentOrder.owner_user_id == user.id, PaymentOrder.status.in_(["creating", "pending"]),
    ).order_by(PaymentOrder.created_at.desc()).limit(1))
    return {"days": 30, "months": 1,
            "reservedDays": reserved_days,
            "amountCents": price_for_package(ad.package_id),
            "packageId": ad.package_id,
            "currency": "EUR", "available": await occupied_slots(session, exclude_id=ad.id, placement=getattr(ad, "placement", "homepage_bottom")) < capacity_for_placement(getattr(ad, "placement", "homepage_bottom"))}


async def checkout(
    session: AsyncSession, user: User, kind: str, target_id: UUID, days: int, amount: int,
    name: str, return_path: str, fingerprint: str | None = None,
    months: int | None = None, duration_hours: int | None = None,
) -> CheckoutResponse:
    require_checkout_enabled(get_settings())
    previous = await session.scalar(
        select(PaymentOrder).where(
            PaymentOrder.owner_user_id == user.id,
            PaymentOrder.kind == kind,
            PaymentOrder.target_id == target_id,
            PaymentOrder.status.in_(["creating", "pending"]),
        ).order_by(PaymentOrder.created_at.desc()).limit(1).with_for_update()
    )
    if previous and previous.checkout_url and previous.stripe_session_id:
        await session.commit()
        remote = await retrieve_stripe_session(previous.stripe_session_id)
        if remote["status"] == "complete":
            if remote.get("payment_status") == "paid":
                await apply_stripe_session(remote, "checkout.session.completed", session)
            raise HTTPException(409, "Payment is awaiting confirmation; do not pay again")
        if remote["status"] == "open":
            if (previous.days == days and previous.amount_cents == amount
                    and getattr(previous, "duration_months", None) == months
                    and getattr(previous, "duration_hours", None) == duration_hours):
                return CheckoutResponse(url=previous.checkout_url, amountCents=amount)
            raise HTTPException(409, "An unfinished payment already exists for this item")
        await apply_stripe_session(remote, "checkout.session.expired", session)
        # The old reservation was released; validate capacity again before replacing it.
        await lock_advertising_capacity(session)
        if kind == "advertisement":
            ad = await session.get(CommercialAdvertisement, target_id)
            if not ad:
                raise HTTPException(404, "Advertisement not found")
            await require_free_slot(session, exclude_id=target_id, placement=ad.placement)
        elif kind == "homepage_hero" and not await slot_available(session):
            raise HTTPException(409, "Homepage placement is currently unavailable")
        elif kind == "listing_top":
            listing = await session.get(Listing, target_id)
            await require_province_top_slot(session, listing, days=days, hours=duration_hours)
    elif previous:
        if (previous.days != days or previous.amount_cents != amount
                or previous.duration_months != months or previous.duration_hours != duration_hours):
            raise HTTPException(409, "An unfinished payment already exists for this item")
        url = await finish_creation(previous, session, create=create_stripe_session)
        return CheckoutResponse(url=url, amountCents=amount)
    if previous:
        previous.status = "expired"
    order = PaymentOrder(
        owner_user_id=user.id, kind=kind, target_id=target_id,
        days=days, amount_cents=amount, status="creating", advertisement_fingerprint=fingerprint,
        duration_months=months, duration_hours=duration_hours,
        checkout_name=name, return_path=return_path,
        top_municipality_code=user.municipality_code if kind == "listing_top" else None,
    )
    session.add(order)
    await session.flush()
    url = await finish_creation(order, session, create=create_stripe_session)
    return CheckoutResponse(url=url, amountCents=amount)


@router.post("/advertisements/{ad_id}/checkout", response_model=CheckoutResponse)
async def advertisement_checkout(
    ad_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
    payload: BannerCheckoutRequest = BannerCheckoutRequest(),
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
    amount = price_for_package(ad.package_id)
    if amount < 50:
        raise HTTPException(503, "Advertisement price has not been configured")
    await require_free_slot(session, exclude_id=ad.id, placement=getattr(ad, "placement", "homepage_bottom"))
    return await checkout(session, user, "advertisement", ad.id, 30, amount,
                          ("Publicidad Premium 112233.es · 1 mes" if ad.package_id == PREMIUM_PACKAGE_ID else "Publicidad 112233.es · 1 mes"),
                          f"/publicidad/{ad.id}/checkout", advertisement_fingerprint(ad), months=1)


@router.get("/homepage/quote")
async def homepage_quote(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    hero = await session.get(HomepageHeroPromotion, 1)
    reservation = await session.scalar(select(PaymentOrder.target_id).where(
        PaymentOrder.kind == "homepage_hero", PaymentOrder.owner_user_id == user.id, PaymentOrder.status.in_(["creating", "pending"]),
    ).limit(1))
    own_hero = await session.scalar(select(Listing.id).where(Listing.id == hero.listing_id, Listing.owner_user_id == user.id)) if hero else None
    return {"amountCents": amount_cents("homepage_hero", 12), "currency": "EUR",
            "offers": offers("homepage_hero"),
            "available": await slot_available(session),
            "reservedListingId": reservation, "featuredListingId": own_hero,
            "endsAt": hero.ends_at if hero and hero.ends_at > datetime.now(UTC) else None}


@router.post("/listings/{listing_id}/homepage/checkout", response_model=CheckoutResponse)
async def homepage_checkout(
    listing_id: UUID, payload: HomepageCheckoutRequest, user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await lock_advertising_capacity(session)
    listing = await session.scalar(select(Listing).where(
        Listing.id == listing_id, Listing.owner_user_id == user.id,
    ).with_for_update())
    if not listing:
        raise HTTPException(404, "Listing not found")
    if not await eligible(listing, session):
        raise HTTPException(409, "Choose a published listing with a photo")
    unresolved = await session.scalar(select(PaymentOrder.id).where(
        PaymentOrder.owner_user_id == user.id, PaymentOrder.kind == "homepage_hero",
        PaymentOrder.status == "paid", PaymentOrder.fulfillment_status == "review_required",
    ).limit(1))
    if unresolved:
        raise HTTPException(409, "Your homepage payment needs review; do not pay again")
    previous = await session.scalar(select(PaymentOrder).where(
        PaymentOrder.kind == "homepage_hero", PaymentOrder.owner_user_id == user.id,
        PaymentOrder.target_id == listing_id, PaymentOrder.status.in_(["creating", "pending"]),
    ).limit(1))
    if not await slot_available(session, exclude_order=previous.id if previous else None):
        raise HTTPException(409, "Homepage placement is currently unavailable")
    hours = payload.durationHours
    return await checkout(session, user, "homepage_hero", listing.id, (hours + 23) // 24,
                          amount_cents("homepage_hero", hours),
                          f"Portada 112233.es · {hours} horas", f"/mis-anuncios?homepage={listing.id}",
                          duration_hours=hours)


@router.get("/listings/{listing_id}/homepage/status")
async def homepage_status(listing_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await lock_advertising_capacity(session)
    listing = await session.scalar(select(Listing.id).where(Listing.id == listing_id, Listing.owner_user_id == user.id))
    if not listing:
        raise HTTPException(404, "Listing not found")
    order = await session.scalar(select(PaymentOrder).where(
        PaymentOrder.kind == "homepage_hero", PaymentOrder.owner_user_id == user.id,
        PaymentOrder.target_id == listing_id,
    ).order_by(PaymentOrder.created_at.desc()).limit(1).with_for_update())
    now = datetime.now(UTC)
    if order and order.status in {"creating", "pending"} and (order.last_reconciled_at is None or order.last_reconciled_at < now - timedelta(seconds=10)):
        order.last_reconciled_at = now
        await session.commit()
        await reconcile_order(order, session, retrieve=retrieve_stripe_session, create=create_stripe_session)
    hero = await session.get(HomepageHeroPromotion, 1)
    return {"orderStatus": order.status if order else None,
            "fulfillmentStatus": order.fulfillment_status if order else None,
            "endsAt": hero.ends_at if hero and hero.listing_id == listing_id and hero.ends_at > now else None}


@router.post("/listings/{listing_id}/homepage/checkout/cancel")
async def cancel_homepage_checkout(listing_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await lock_advertising_capacity(session)
    order = await session.scalar(select(PaymentOrder).where(
        PaymentOrder.kind == "homepage_hero", PaymentOrder.owner_user_id == user.id,
        PaymentOrder.target_id == listing_id, PaymentOrder.status.in_(["creating", "pending"]),
    ).limit(1).with_for_update())
    if order:
        if not order.stripe_session_id:
            await finish_creation(order, session, create=create_stripe_session)
        await session.commit()
        remote = await expire_stripe_session(cast(str, order.stripe_session_id))
        if remote["status"] == "complete" and remote.get("payment_status") == "paid":
            await apply_stripe_session(remote, "checkout.session.completed", session)
            return {"cancelled": False}
        if remote["status"] != "expired":
            raise HTTPException(409, "Payment is awaiting confirmation; do not pay again")
        await apply_stripe_session(remote, "checkout.session.expired", session)
    return {"cancelled": True}


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
    if not await eligible(listing, session):
        raise HTTPException(409, "Only your published listing can be promoted")
    promotion = await session.get(ListingPromotion, listing.id)
    if promotion and promotion.ends_at is None:
        raise HTTPException(409, "Permanent TOP needs support review before purchase")
    unresolved = await session.scalar(select(PaymentOrder.id).where(
        PaymentOrder.kind == "listing_top", PaymentOrder.target_id == listing.id,
        PaymentOrder.owner_user_id == user.id, PaymentOrder.status == "paid",
        PaymentOrder.fulfillment_status == "review_required",
    ).limit(1))
    if unresolved:
        raise HTTPException(409, "Your TOP payment needs review; do not pay again")
    hours = payload.durationHours
    await require_province_top_slot(session, listing, hours=hours)
    return await checkout(session, user, "listing_top", listing.id, (hours + 23) // 24,
                          amount_cents("listing_top", hours),
                          f"TOP 112233.es · {hours} horas", f"/mis-anuncios?top={listing.id}",
                          duration_hours=hours)


@router.get("/listings/{listing_id}/top/availability")
async def listing_top_availability(
    listing_id: UUID, durationHours: int | None = Query(default=None),
    days: int = Query(default=10, ge=10, le=365),
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
):
    listing = await session.scalar(select(Listing).where(Listing.id == listing_id, Listing.owner_user_id == user.id))
    if not listing:
        raise HTTPException(404, "Listing not found")
    if durationHours is not None and durationHours not in (12, 24, 72):
        raise HTTPException(422, "Choose a supported TOP duration: 12, 24 or 72 hours")
    return await top_availability(session, listing, days=days, hours=durationHours)


@router.get("/listings/{listing_id}/top/status")
async def top_payment_status(listing_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await lock_advertising_capacity(session)
    listing = await session.scalar(select(Listing.id).where(Listing.id == listing_id, Listing.owner_user_id == user.id))
    if not listing:
        raise HTTPException(404, "Listing not found")
    order = await session.scalar(select(PaymentOrder).where(
        PaymentOrder.kind == "listing_top", PaymentOrder.target_id == listing_id, PaymentOrder.owner_user_id == user.id,
    ).order_by(PaymentOrder.created_at.desc()).limit(1).with_for_update())
    now = datetime.now(UTC)
    if order and order.status in {"creating", "pending"} and (order.last_reconciled_at is None or order.last_reconciled_at < now - timedelta(seconds=10)):
        order.last_reconciled_at = now
        await session.commit()
        await reconcile_order(order, session, retrieve=retrieve_stripe_session, create=create_stripe_session)
    promotion = await session.get(ListingPromotion, listing_id)
    return {"orderStatus": order.status if order else None,
            "fulfillmentStatus": order.fulfillment_status if order else None,
            "endsAt": promotion.ends_at if promotion else None}


@router.post("/listings/{listing_id}/top/checkout/cancel")
async def cancel_top_checkout(listing_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await lock_advertising_capacity(session)
    order = await session.scalar(select(PaymentOrder).where(
        PaymentOrder.kind == "listing_top", PaymentOrder.target_id == listing_id,
        PaymentOrder.owner_user_id == user.id, PaymentOrder.status.in_(["creating", "pending"]),
    ).order_by(PaymentOrder.created_at.desc()).limit(1).with_for_update())
    if order:
        if not order.stripe_session_id:
            await finish_creation(order, session, create=create_stripe_session)
        await session.commit()
        remote = await expire_stripe_session(cast(str, order.stripe_session_id))
        if remote["status"] == "complete" and remote.get("payment_status") == "paid":
            await apply_stripe_session(remote, "checkout.session.completed", session)
            return {"cancelled": False}
        if remote["status"] != "expired":
            raise HTTPException(409, "Payment is awaiting confirmation; do not pay again")
        await apply_stripe_session(remote, "checkout.session.expired", session)
    return {"cancelled": True}


@router.post("/stripe/webhook")
async def stripe_webhook(
    request: Request, stripe_signature: str = Header(default="", alias="Stripe-Signature"),
    session: AsyncSession = Depends(get_session),
):
    event = verified_stripe_event(await request.body(), stripe_signature)
    event_type = event["type"]
    if event_type.startswith("charge.") or event_type in {"refund.created", "refund.updated", "refund.failed"}:
        from ...services.payment_finances import financial_webhook
        return await financial_webhook(event, session)
    if event_type not in {"checkout.session.completed", "checkout.session.async_payment_succeeded",
                          "checkout.session.async_payment_failed", "checkout.session.expired"}:
        return {"received": True}
    data = event.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("object"), dict):
        raise HTTPException(400, "Invalid Stripe event")
    checkout_session = data["object"]
    if event_type not in {"checkout.session.expired", "checkout.session.async_payment_failed"} and checkout_session.get("payment_status") != "paid":
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
    if order and order.status in {"creating", "pending"} and (order.last_reconciled_at is None or order.last_reconciled_at < now - timedelta(seconds=10)):
        order.last_reconciled_at = now
        await session.commit()
        try:
            await reconcile_order(order, session, retrieve=retrieve_stripe_session, create=create_stripe_session)
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
        PaymentOrder.kind == "advertisement", PaymentOrder.status.in_(["creating", "pending"]),
    ).order_by(PaymentOrder.created_at.desc()).limit(1).with_for_update())
    if order:
        if not order.stripe_session_id:
            await finish_creation(order, session, create=create_stripe_session)
        await session.commit()
        remote = await expire_stripe_session(cast(str, order.stripe_session_id))
        if remote["status"] == "complete" and remote.get("payment_status") == "paid":
            await apply_stripe_session(remote, "checkout.session.completed", session)
            return {"cancelled": False, "paid": True}
        if remote["status"] != "expired":
            raise HTTPException(409, "Payment is awaiting confirmation; do not pay again")
        await apply_stripe_session(remote, "checkout.session.expired", session)
    return {"cancelled": True, "paid": ad.payment_status == "paid"}


@router.get("/admin/review-required")
async def payment_review_queue(user: User = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    orders = (await session.scalars(select(PaymentOrder).where(
        PaymentOrder.fulfillment_status == "review_required",
    ).order_by(PaymentOrder.paid_at.desc()).limit(100))).all()
    return [{"id": str(order.id), "kind": order.kind, "targetId": str(order.target_id),
             "amountCents": order.amount_cents, "paidAt": order.paid_at, "note": order.fulfillment_note,
             "status":order.status,"financialStatus":order.financial_status,"stripeSessionId":order.stripe_session_id}
            for order in orders]


class PaymentResolutionRequest(BaseModel):
    action: Literal["refund", "restore", "reconcile"]
    reason: str = Field(min_length=10, max_length=1000)
    stripeSessionId: str | None = Field(default=None, max_length=255)


@router.post("/admin/orders/{order_id}/resolve")
async def resolve_order(order_id: UUID, payload: PaymentResolutionRequest, user: User = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    from ...services.payment_finances import reconcile_unknown_session, resolve_payment
    if len(payload.reason.strip()) < 10:
        raise HTTPException(422, "A resolution reason of at least 10 characters is required")
    if payload.action == "reconcile":
        return await reconcile_unknown_session(order_id, user, payload.reason.strip(), payload.stripeSessionId, session)
    return await resolve_payment(order_id, user, payload.reason.strip(), payload.action, session)
