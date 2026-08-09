from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Listing, User
from ..models.moderation import ListingRestriction
from ..schemas.admin import AdminListingResponse
from .admin import public_listing
from .moderation import active_window


async def _active_restrictions_by_listing(
    session: AsyncSession,
    listing_ids: list[UUID],
) -> dict[UUID, ListingRestriction]:
    """Load active restrictions for an admin page with one query."""
    if not listing_ids:
        return {}
    rows = (
        await session.scalars(
            select(ListingRestriction)
            .where(
                ListingRestriction.listing_id.in_(listing_ids),
                *active_window(ListingRestriction),
            )
            .order_by(
                ListingRestriction.listing_id,
                ListingRestriction.ends_at.desc(),
                ListingRestriction.starts_at.desc(),
            )
        )
    ).all()
    result: dict[UUID, ListingRestriction] = {}
    for row in rows:
        result.setdefault(row.listing_id, row)
    return result


async def list_listings(
    session: AsyncSession,
    status: str | None,
    search: str | None,
    *,
    restricted: bool | None = None,
    limit: int,
    offset: int,
) -> list[AdminListingResponse]:
    """Return actionable listings with filters applied before pagination."""
    query = (
        select(Listing, User)
        .join(User, User.id == Listing.owner_user_id)
        .where(Listing.deleted_at.is_(None))
        .order_by(Listing.created_at.desc(), Listing.id.desc())
    )
    if status:
        query = query.where(Listing.status == status)
    if search:
        term = f"%{search.strip()}%"
        query = query.where(Listing.title.ilike(term) | User.name.ilike(term))
    active_restriction = (
        select(ListingRestriction.id)
        .where(ListingRestriction.listing_id == Listing.id, *active_window(ListingRestriction))
        .correlate(Listing)
        .exists()
    )
    if restricted is True:
        query = query.where(active_restriction)
    elif restricted is False:
        query = query.where(~active_restriction)

    rows = (await session.execute(query.limit(limit).offset(offset))).all()
    restrictions = await _active_restrictions_by_listing(
        session,
        [listing.id for listing, _ in rows],
    )
    return [
        public_listing(
            listing,
            owner=owner,
            restriction=restrictions.get(listing.id),
        )
        for listing, owner in rows
    ]
