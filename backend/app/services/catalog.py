from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import CatalogState


async def touch_catalog(session: AsyncSession) -> None:
    """Atomically invalidate cached public-listing state inside the caller transaction.

    The catalog row is a coarse invalidation token, not a business counter. An
    upsert avoids both the missing-row race and lost increments from concurrent
    visibility changes while preserving the historical first-touch value of 2.
    """
    now = datetime.now(UTC)
    statement = (
        insert(CatalogState)
        .values(id=1, version=2, updated_at=now)
        .on_conflict_do_update(
            index_elements=[CatalogState.id],
            set_={
                "version": CatalogState.version + 1,
                "updated_at": now,
            },
        )
    )
    await session.execute(statement)
