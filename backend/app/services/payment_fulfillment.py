"""One fulfillment path for signed webhooks and authenticated Stripe GET recovery."""
import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from ..core.config import get_settings
from ..models import Listing, User
from ..models.commercial_advertisement import CommercialAdvertisement
from ..models.moderation import ListingPromotion
from ..models.payment_order import PaymentOrder
from .commercial_advertisements import MAX_ACTIVE_HOMEPAGE_ADS, lock_advertising_capacity, occupied_slots
from .notifications import create_notification
from .homepage_purchase import eligible, one_month_after, slot_available
from ..models.moderation import HomepageHeroPromotion
from .catalog import touch_catalog

logger = logging.getLogger(__name__)


def advertisement_fingerprint(ad) -> str:
    values = {key: str(getattr(ad, key, "")) for key in (
        "id", "owner_user_id", "image_asset_id", "title", "description", "destination_type", "destination", "package_id",
    )}
    return hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


async def notify_payment(session, order, kind: str, title: str, body: str) -> None:
    recipient = await session.get(User, order.owner_user_id)
    if recipient and recipient.deleted_at is None:
        await create_notification(session, recipient=recipient, kind=kind, title=title, body=body,
                                  idempotency_key=f"payment:{order.id}:{kind}")


async def apply_stripe_session(checkout_session: dict, event_type: str, session) -> dict:
    try:
        order_uuid = UUID(checkout_session.get("client_reference_id"))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(400, "Unknown payment order") from None
    await lock_advertising_capacity(session)
    order = await session.scalar(select(PaymentOrder).where(PaymentOrder.id == order_uuid).with_for_update().execution_options(populate_existing=True))
    if not order or order.stripe_session_id != checkout_session.get("id"):
        raise HTTPException(400, "Unknown payment order")
    expected_live = get_settings().stripe_secret_key.startswith("sk_live_")
    if (type(checkout_session.get("amount_total")) is not int
            or checkout_session["amount_total"] != order.amount_cents
            or checkout_session.get("currency") != "eur"
            or checkout_session.get("livemode") is not expected_live):
        raise HTTPException(400, "Payment does not match order")
    if order.status == "paid":
        return {"received": True}
    if event_type == "checkout.session.expired":
        if order.status == "pending":
            order.status = "expired"
            await session.commit()
        return {"received": True}
    if checkout_session.get("payment_status") != "paid":
        return {"received": True}
    was_expired = order.status == "expired"
    order.status = "paid"
    order.paid_at = datetime.now(UTC)
    order.fulfillment_status = "fulfilled"
    if order.kind == "advertisement":
        ad = await session.scalar(select(CommercialAdvertisement).where(
            CommercialAdvertisement.id == order.target_id,
            CommercialAdvertisement.owner_user_id == order.owner_user_id,
        ).with_for_update())
        valid = bool(ad and ad.status == "pending_payment" and ad.payment_status == "unpaid")
        if valid and getattr(order, "advertisement_fingerprint", None):
            valid = order.advertisement_fingerprint == advertisement_fingerprint(ad)
        if valid and was_expired:
            # A released reservation cannot displace seven current purchases.
            valid = bool(getattr(order, "advertisement_fingerprint", None)) and (
                await occupied_slots(session, exclude_id=ad.id) < MAX_ACTIVE_HOMEPAGE_ADS
            )
        if valid:
            ad.duration_days = order.days
            ad.payment_status = "paid"
            ad.status = "pending_review"
            ad.submitted_at = order.paid_at
            await notify_payment(session, order, "advertisement_paid", "Pago publicitario confirmado",
                                 "Tu publicidad está pagada y pendiente de revisión. El plazo empieza tras la aprobación.")
        else:
            order.fulfillment_status = "review_required"
            order.fulfillment_note = "Paid advertising order cannot be safely assigned; check creative, capacity and refund."
    elif order.kind == "homepage_hero":
        listing = await session.scalar(select(Listing).where(
            Listing.id == order.target_id, Listing.owner_user_id == order.owner_user_id,
        ).with_for_update())
        if await eligible(listing, session) and await slot_available(session, exclude_order=order.id):
            hero = await session.get(HomepageHeroPromotion, 1)
            if hero is None:
                hero = HomepageHeroPromotion(id=1)
                session.add(hero)
            hero.listing_id = listing.id
            hero.starts_at = order.paid_at
            hero.ends_at = one_month_after(order.paid_at)
            hero.configured_by = None
            hero.configured_at = order.paid_at
            await touch_catalog(session)
            await notify_payment(session, order, "homepage_hero_paid", "Tu anuncio está en portada",
                                 "El pago está confirmado. Tu anuncio aparecerá en la portada durante un mes.")
        else:
            order.fulfillment_status = "review_required"
            order.fulfillment_note = "Paid homepage placement no longer eligible or slot occupied; reconcile or refund."
    elif order.kind == "listing_top":
        listing = await session.scalar(select(Listing).where(
            Listing.id == order.target_id, Listing.owner_user_id == order.owner_user_id,
        ).with_for_update())
        if listing and listing.status == "published" and not listing.is_external and listing.deleted_at is None:
            promotion = await session.scalar(select(ListingPromotion).where(
                ListingPromotion.listing_id == listing.id,
            ).with_for_update())
            start = max(order.paid_at, promotion.ends_at) if promotion and promotion.ends_at else order.paid_at
            if promotion and promotion.ends_at is None:
                order.fulfillment_status = "review_required"
                order.fulfillment_note = "Legacy permanent TOP requires manual reconciliation."
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
                    total_price_cents=order.amount_cents,
                ))
        else:
            order.fulfillment_status = "review_required"
            order.fulfillment_note = "Paid TOP listing no longer eligible."
    if order.fulfillment_status == "review_required":
        logger.error("stripe_paid_order_requires_review order_id=%s", order.id)
        await notify_payment(session, order, "payment_review_required", "Tu pago necesita una revisión",
                             "El pago se ha recibido, pero no hemos podido activar el servicio. Contacta con soporte; no vuelvas a pagar.")
    await session.commit()
    return {"received": True}
