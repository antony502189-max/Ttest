from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Listing, User
from ..models.moderation import ListingRestriction
from ..schemas.admin import AdminListingResponse
from .admin import public_listing
from .moderation import active_listing_restriction, active_window


async def list_listings(
    session: AsyncSession,
    status: str | None,
    search: str | None,
    *,
    restricted: bool | None = None,
    limit: int,
    offset: int,
) -> list[AdminListingResponse]:
    """Return only actionable listings in the moderation console."""
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
    result: list[AdminListingResponse] = []
    for listing, owner in rows:
        restriction = await active_listing_restriction(listing.id, session)
        result.append(public_listing(listing, owner=owner, restriction=restriction))
    return result
