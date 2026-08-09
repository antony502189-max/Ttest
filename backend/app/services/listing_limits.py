from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..models import Listing, User
from .moderation import is_admin

ACTIVE_LISTING_STATUSES = {"draft", "pending", "published", "hidden"}


async def enforce_listing_creation_limits(user: User, session: AsyncSession) -> None:
    """Serialize and bound manual listing creation unless active admin access is present.

    The legacy product role is not an authorization boundary. Revoking an
    account from `admin_access` immediately restores normal abuse-prevention
    quotas even if an older user row still carries role="admin".
    """
    if await is_admin(user, session):
        return

    settings = get_settings()
    now = datetime.now(UTC)
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"listing-create:{user.id}"},
    )
    active_count, recent_count = (
        await session.execute(
            select(
                select(func.count())
                .select_from(Listing)
                .where(
                    Listing.owner_user_id == user.id,
                    Listing.deleted_at.is_(None),
                    Listing.status.in_(ACTIVE_LISTING_STATUSES),
                )
                .scalar_subquery(),
                select(func.count())
                .select_from(Listing)
                .where(
                    Listing.owner_user_id == user.id,
                    Listing.created_at > now - timedelta(days=1),
                )
                .scalar_subquery(),
            )
        )
    ).one()

    if int(active_count) >= settings.max_active_listings_per_user:
        raise HTTPException(409, "Active listing limit reached")
    if int(recent_count) >= settings.max_listing_creations_per_day:
        raise HTTPException(429, "Daily listing creation limit reached")
