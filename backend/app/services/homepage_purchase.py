"""Serialize purchases of the existing single homepage photo slot."""
from calendar import monthrange
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select

from ..models import ListingImage, MediaAsset, User
from ..models.moderation import HomepageHeroPromotion
from ..models.payment_order import PaymentOrder
from .commercial_advertisements import lock_advertising_capacity
from .moderation import active_listing_restriction, active_user_restriction
from .rental_price_limit import require_listing_price

PRICE_CENTS = 6000


def one_month_after(start):
    year, month = (start.year + 1, 1) if start.month == 12 else (start.year, start.month + 1)
    return start.replace(year=year, month=month, day=min(start.day, monthrange(year, month)[1]))


async def eligible(listing, session):
    if listing is None:
        return False
    try:
        require_listing_price(listing)
    except HTTPException:
        return False
    owner = await session.get(User, listing.owner_user_id)
    return bool(listing and listing.status == "published" and not listing.is_external
                and listing.deleted_at is None
                and owner and owner.deleted_at is None and not owner.blocked
                and not await active_listing_restriction(listing.id, session)
                and not await active_user_restriction(listing.owner_user_id, session)
                and await session.scalar(select(ListingImage.listing_id).join(MediaAsset, MediaAsset.id == ListingImage.media_asset_id).where(ListingImage.listing_id == listing.id, MediaAsset.deleted_at.is_(None)).limit(1)))


async def slot_available(session, *, exclude_order=None):
    hero = await session.get(HomepageHeroPromotion, 1)
    if hero and hero.ends_at > datetime.now(UTC):
        return False
    query = select(PaymentOrder.id).where(PaymentOrder.kind == "homepage_hero", PaymentOrder.status == "pending")
    if exclude_order is not None:
        query = query.where(PaymentOrder.id != exclude_order)
    return await session.scalar(query.limit(1)) is None


async def protect_purchased_slot(session):
    await lock_advertising_capacity(session)
    pending = await session.scalar(select(PaymentOrder.id).where(
        PaymentOrder.kind == "homepage_hero", PaymentOrder.status == "pending",
    ).limit(1))
    hero = await session.get(HomepageHeroPromotion, 1)
    paid = None
    if hero and hero.ends_at > datetime.now(UTC):
        paid = await session.scalar(select(PaymentOrder.id).where(
            PaymentOrder.kind == "homepage_hero", PaymentOrder.target_id == hero.listing_id,
            PaymentOrder.status == "paid", PaymentOrder.fulfillment_status == "fulfilled",
            PaymentOrder.paid_at >= hero.starts_at,
        ).limit(1))
    if pending or paid:
        raise HTTPException(409, "Homepage placement is reserved by a purchase")
