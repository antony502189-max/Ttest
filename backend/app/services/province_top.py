"""Three TOP listings per verified owner municipality, including checkouts.

The module name is retained for existing internal callers of the province rollout.

Callers hold lock_advertising_capacity until their reservation is committed.
Provider reservations are never released by a local clock.
"""
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select

from ..models import User
from ..models.moderation import ListingPromotion
from ..models.payment_order import PaymentOrder
from ..spain_provinces import address_province_code
from .address_geography import MUNICIPALITIES

MAX_PROVINCE_TOP = 3


def next_available(windows, start, end):
    """Find the first interval of the requested length with fewer than 3 peers.

    Windows belonging to one listing count once, even during a renewal checkout.
    Half-open windows allow a new purchase at the exact expiry instant.
    """
    duration = end - start
    candidates = sorted({start, *(finish for _, _, finish in windows if finish is not None and finish > start)})
    for candidate in candidates:
        finish = candidate + duration
        checkpoints = {candidate, *(begin for _, begin, _ in windows if candidate < begin < finish)}
        if all(len({key for key, begin, until in windows if begin <= point and (until is None or point < until)}) < MAX_PROVINCE_TOP
               for point in checkpoints):
            return candidate
    return None


async def top_availability(session, listing, *, days=10, starts_at=None, ends_at=None, exclude_order=None, months=None):
    now = datetime.now(UTC)
    owner = await session.get(User, listing.owner_user_id, populate_existing=True)
    code = owner.municipality_code if owner and owner.address_verified_at else None
    if code not in MUNICIPALITIES:
        raise HTTPException(409, "Verify the owner's address in the profile before buying TOP")
    start = starts_at or now
    end = ends_at or start + timedelta(days=days)
    if ends_at is None:
        current = await session.get(ListingPromotion, listing.id)
        extension_start = max(start, current.ends_at) if current and current.ends_at else start
        if months == 1:
            from .homepage_purchase import one_month_after
            end = one_month_after(extension_start)
        else:
            end = extension_start + timedelta(days=days)
    # Freeze the municipality at reservation/grant time. A missing legacy
    # association is never guessed from the property's postcode.
    unknown_promotion = await session.scalar(select(ListingPromotion.listing_id).where(
        ListingPromotion.top_municipality_code.is_(None),
        (ListingPromotion.ends_at.is_(None)) | (ListingPromotion.ends_at > now),
    ).limit(1))
    unknown_order = await session.scalar(select(PaymentOrder.id).where(
        PaymentOrder.kind == "listing_top", PaymentOrder.status.in_(["creating", "pending"]),
        PaymentOrder.top_municipality_code.is_(None),
    ).limit(1))
    if unknown_promotion or unknown_order:
        raise HTTPException(409, "Existing TOP municipality associations require operator reconciliation")
    promotions = (await session.execute(select(
        ListingPromotion.listing_id, ListingPromotion.starts_at, ListingPromotion.ends_at,
    ).where(ListingPromotion.top_municipality_code == code,
            (ListingPromotion.ends_at.is_(None)) | (ListingPromotion.ends_at > start)))).all()
    orders_query = select(PaymentOrder.target_id).where(
        PaymentOrder.kind == "listing_top", PaymentOrder.top_municipality_code == code,
        PaymentOrder.status.in_(["creating", "pending"]),
    )
    if exclude_order:
        orders_query = orders_query.where(PaymentOrder.id != exclude_order)
    reservations = (await session.scalars(orders_query)).all()
    windows = [(key, begin, finish) for key, begin, finish in promotions]
    windows.extend((key, now, None) for key in reservations)
    available_at = next_available([window for window in windows if window[0] != listing.id], start, end)
    occupied = len({key for key, begin, finish in windows if begin <= start and (finish is None or finish > start)})
    return {"municipalityCode": code, "municipality": MUNICIPALITIES[code], "capacity": MAX_PROVINCE_TOP,
            "available": available_at == start, "availableSlots": max(0, MAX_PROVINCE_TOP - occupied),
            "availableAt": available_at, "serverNow": now}


async def require_province_top_slot(session, listing, **kwargs):
    availability = await top_availability(session, listing, **kwargs)
    if not availability["available"]:
        raise HTTPException(409, "All TOP places in the owner's municipality are occupied")
    return availability


async def require_top_address_mutable(session, listing, postcode):
    if address_province_code(listing.postcode) == address_province_code(postcode):
        return
    promotion = await session.get(ListingPromotion, listing.id)
    if promotion and (promotion.ends_at is None or promotion.ends_at > datetime.now(UTC)):
        raise HTTPException(409, "The province cannot change while this listing has TOP")
    pending = await session.scalar(select(PaymentOrder.id).where(
        PaymentOrder.target_id == listing.id, PaymentOrder.kind == "listing_top",
        PaymentOrder.status.in_(["creating", "pending"]),
    ).limit(1))
    if pending:
        raise HTTPException(409, "Cancel the pending TOP payment before changing province")


async def protect_purchased_top(session, listing_id):
    """Legacy admin projection edits cannot alter a live payment entitlement.

    Callers hold the advertising lock, including when the projection is missing.
    Financial resolution keeps the original service interval and audit history.
    """
    now = datetime.now(UTC)
    reserved = await session.scalar(select(PaymentOrder.id).where(
        PaymentOrder.kind == "listing_top", PaymentOrder.target_id == listing_id,
        (PaymentOrder.status.in_(["creating", "pending"])) | (
            (PaymentOrder.status == "paid")
            & PaymentOrder.financial_status.notin_(["refunded", "dispute_lost"])
            & ((PaymentOrder.service_ends_at.is_(None)) | (PaymentOrder.service_ends_at > now))
        ),
    ).limit(1))
    if reserved:
        raise HTTPException(409, "TOP is reserved by a purchase; use audited payment review/refund/restore")
