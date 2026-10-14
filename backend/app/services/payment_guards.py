"""Deletion is explicit: settle open/unused purchases before destroying targets."""
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select

from ..models.commercial_advertisement import CommercialAdvertisement
from ..models.moderation import HomepageHeroPromotion, ListingPromotion
from ..models.payment_order import PaymentOrder


async def protect_payment_deletion(session, *, owner_id=None, target_id=None):
    now = datetime.now(UTC)
    query = select(PaymentOrder).where(PaymentOrder.owner_user_id == owner_id if owner_id is not None else PaymentOrder.target_id == target_id)
    orders = (await session.scalars(query)).all()
    for order in orders:
        if order.status in {"creating", "pending"} or order.financial_status in {"refund_pending", "disputed"} or (order.status == "paid" and order.fulfillment_status == "review_required"):
            raise HTTPException(409, "Settle pending payments or refunds before deleting")
        if order.status != "paid" or order.financial_status != "normal":
            continue
        if order.service_ends_at and order.service_ends_at > now:
            raise HTTPException(409, "Active paid services must expire or be refunded before deleting")
        if order.kind == "advertisement":
            ad = await session.get(CommercialAdvertisement, order.target_id)
            active = ad and ad.payment_status == "paid" and (ad.ends_at is None or ad.ends_at > now)
        elif order.kind == "homepage_hero":
            hero = await session.get(HomepageHeroPromotion, 1)
            active = hero and hero.listing_id == order.target_id and hero.ends_at > now
        else:
            promotion = await session.get(ListingPromotion, order.target_id)
            active = promotion and (promotion.ends_at is None or promotion.ends_at > now)
        if active:
            raise HTTPException(409, "Active paid services must expire or be refunded before deleting")
