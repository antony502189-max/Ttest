from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Listing, User
from ..models.moderation import ListingPromotion, ListingRestriction
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
    after_created_at: datetime | None = None,
    after_id: UUID | None = None,
) -> list[AdminListingResponse]:
    """Return actionable listings with offset or seek pagination.

    A soft-deleted owner makes every remaining listing historical rather than an
    actionable moderation target. Keep those rows out of the active moderation
    queue; report history resolves its own owner/listing context separately.
    """
    query = (
        select(Listing, User, ListingPromotion)
        .join(User, User.id == Listing.owner_user_id)
        .outerjoin(ListingPromotion, ListingPromotion.listing_id == Listing.id)
        .where(
            Listing.deleted_at.is_(None),
            User.deleted_at.is_(None),
        )
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

    if after_created_at is not None and after_id is not None:
        query = query.where(
            or_(
                Listing.created_at < after_created_at,
                and_(Listing.created_at == after_created_at, Listing.id < after_id),
            )
        )
        offset = 0

    rows = (await session.execute(query.limit(limit).offset(offset))).all()
    restrictions = await _active_restrictions_by_listing(
        session,
        [listing.id for listing, _, _ in rows],
    )
    return [
        public_listing(
            listing,
            owner=owner,
            restriction=restrictions.get(listing.id),
            promotion=promotion,
        )
        for listing, owner, promotion in rows
    ]
