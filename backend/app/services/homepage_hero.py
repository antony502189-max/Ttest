from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import ceil
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Listing, ListingImage, User
from ..models.moderation import HomepageHeroPromotion
from ..repositories.listings import response_from, visible_query
from ..schemas.admin import HomepageHeroPromotionResponse
from ..schemas.listings import ListingResponse
from .admin import _actionable_listing, audit
from .catalog import touch_catalog
from .moderation import active_listing_restriction, active_user_restriction

HOMEPAGE_HERO_SINGLETON_ID = 1
DEFAULT_HOMEPAGE_HERO_DAYS = 7


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def homepage_hero_response(row: HomepageHeroPromotion) -> HomepageHeroPromotionResponse:
    now = datetime.now(UTC)
    if row.starts_at > now:
        state = "scheduled"
    elif now >= row.ends_at:
        state = "expired"
    else:
        state = "active"
    days = max(1, ceil((row.ends_at - row.starts_at).total_seconds() / 86_400))
    return HomepageHeroPromotionResponse(
        listingId=row.listing_id,
        startsAt=row.starts_at,
        endsAt=row.ends_at,
        state=state,
        days=days,
    )


async def get_admin_homepage_hero(session: AsyncSession) -> HomepageHeroPromotionResponse | None:
    row = await session.get(HomepageHeroPromotion, HOMEPAGE_HERO_SINGLETON_ID)
    return homepage_hero_response(row) if row else None


async def configure_homepage_hero(
    listing_id: UUID,
    actor: User,
    session: AsyncSession,
    *,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
) -> HomepageHeroPromotionResponse:
    listing, owner = await _actionable_listing(listing_id, session)
    if listing.status != "published":
        raise HTTPException(409, "Only published listings can be featured on the homepage")
    if await active_listing_restriction(listing.id, session) or await active_user_restriction(owner.id, session):
        raise HTTPException(409, "Only publicly eligible listings can be featured on the homepage")
    image_exists = await session.scalar(
        select(ListingImage.listing_id).where(ListingImage.listing_id == listing.id).limit(1)
    )
    if not image_exists:
        raise HTTPException(409, "Homepage promotion requires at least one listing image")

    now = datetime.now(UTC)
    start = now if starts_at is None else _as_utc(starts_at)
    if start < now:
        if start.date() == now.date():
            start = now
        else:
            raise HTTPException(422, "Homepage promotion start date cannot be in the past")

    end = start + timedelta(days=DEFAULT_HOMEPAGE_HERO_DAYS) if ends_at is None else _as_utc(ends_at)
    if end <= start:
        raise HTTPException(422, "Homepage promotion end date must be after its start date")

    row = await session.scalar(
        select(HomepageHeroPromotion)
        .where(HomepageHeroPromotion.id == HOMEPAGE_HERO_SINGLETON_ID)
        .with_for_update()
    )
    previous = None
    if row is None:
        row = HomepageHeroPromotion(
            id=HOMEPAGE_HERO_SINGLETON_ID,
            listing_id=listing.id,
            starts_at=start,
            ends_at=end,
            configured_by=actor.id,
        )
        session.add(row)
    else:
        previous = {
            "listingId": str(row.listing_id),
            "startsAt": row.starts_at.isoformat(),
            "endsAt": row.ends_at.isoformat(),
        }
        row.listing_id = listing.id
        row.starts_at = start
        row.ends_at = end
        row.configured_by = actor.id
        row.configured_at = now

    session.add(audit(
        actor.id,
        "homepage_hero.configured",
        "listing",
        listing.id,
        {
            "previous": previous,
            "startsAt": start.isoformat(),
            "endsAt": end.isoformat(),
        },
    ))
    await touch_catalog(session)
    await session.commit()
    return homepage_hero_response(row)


async def remove_homepage_hero(actor: User, session: AsyncSession) -> None:
    row = await session.scalar(
        select(HomepageHeroPromotion)
        .where(HomepageHeroPromotion.id == HOMEPAGE_HERO_SINGLETON_ID)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "Homepage promotion is not configured")
    listing_id = row.listing_id
    detail = {"startsAt": row.starts_at.isoformat(), "endsAt": row.ends_at.isoformat()}
    await session.delete(row)
    session.add(audit(actor.id, "homepage_hero.removed", "listing", listing_id, detail))
    await touch_catalog(session)
    await session.commit()


async def get_active_homepage_hero_listing(session: AsyncSession) -> ListingResponse | None:
    now = datetime.now(UTC)
    promotion = await session.scalar(
        select(HomepageHeroPromotion).where(
            HomepageHeroPromotion.id == HOMEPAGE_HERO_SINGLETON_ID,
            HomepageHeroPromotion.starts_at <= now,
            HomepageHeroPromotion.ends_at > now,
        )
    )
    if promotion is None:
        return None
    row = (await session.execute(visible_query().where(Listing.id == promotion.listing_id))).one_or_none()
    if row is None:
        return None
    response = response_from(row)
    return response if response.imageUrls else None
