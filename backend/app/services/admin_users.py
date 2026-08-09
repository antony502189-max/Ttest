from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuthSession, Listing, User
from ..models.moderation import AdminAccess, UserRestriction
from ..schemas.admin import AdminUserResponse
from .admin import public_user
from .moderation import active_user_restriction, active_window, normalize_email


async def _active_admin_emails(session: AsyncSession) -> set[str]:
    return set((await session.scalars(select(AdminAccess.email).where(AdminAccess.active.is_(True)))).all())


def _active_restriction_exists(*, restriction_type: str | None = None):
    query = select(UserRestriction.id).where(
        UserRestriction.user_id == User.id,
        *active_window(UserRestriction),
    )
    if restriction_type:
        query = query.where(UserRestriction.restriction_type == restriction_type)
    return query.correlate(User).exists()


async def list_users(
    session: AsyncSession,
    search: str | None,
    *,
    status_filter: str | None = None,
    limit: int,
    offset: int,
) -> list[AdminUserResponse]:
    """List admin users with every filter applied before LIMIT/OFFSET.

    The old implementation paginated first and discarded non-matching rows in
    Python. That could return a short first page even when matching users
    existed on later pages and caused clients to stop draining prematurely.
    """
    listing_count = (
        select(func.count(Listing.id))
        .where(Listing.owner_user_id == User.id, Listing.deleted_at.is_(None))
        .correlate(User)
        .scalar_subquery()
    )
    last_login = (
        select(func.max(AuthSession.issued_at))
        .where(AuthSession.user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )
    query = select(User, listing_count, last_login).order_by(User.created_at.desc(), User.id.desc())
    if search:
        query = query.where(User.name.ilike(f"%{search.strip()}%"))

    if status_filter == "deleted":
        query = query.where(User.deleted_at.is_not(None))
    else:
        query = query.where(User.deleted_at.is_(None))
        if status_filter == "restricted":
            query = query.where(_active_restriction_exists())
        elif status_filter in {"full", "publish", "view_listings"}:
            query = query.where(_active_restriction_exists(restriction_type=status_filter))
        elif status_filter == "active":
            query = query.where(~_active_restriction_exists(), User.blocked.is_(False))

    rows = (await session.execute(query.limit(limit).offset(offset))).all()
    admin_emails = await _active_admin_emails(session)
    result: list[AdminUserResponse] = []
    for user, count, last_seen in rows:
        restriction = await active_user_restriction(user.id, session)
        result.append(
            public_user(
                user,
                listing_count=int(count or 0),
                last_login=last_seen,
                restriction=restriction,
                is_admin=normalize_email(user.email) in admin_emails,
            )
        )
    return result
