from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User


async def lock_user_for_mutation(user_id: UUID, session: AsyncSession) -> User | None:
    """Return authoritative user state under the account-mutation row lock.

    Request dependencies commonly place ``User`` in the session identity map.
    ``populate_existing`` is required so a lock acquired after a concurrent
    account deletion cannot return stale active attributes from that cache.
    """
    return await session.scalar(
        select(User)
        .where(User.id == user_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )
