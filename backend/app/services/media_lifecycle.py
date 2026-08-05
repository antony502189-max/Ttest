from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import MediaAsset


async def lock_media_assets(session: AsyncSession, asset_ids: set[UUID]) -> list[MediaAsset]:
    """Lock media rows in a deterministic order before changing their references."""
    ordered_ids = sorted(asset_ids, key=str)
    if not ordered_ids:
        return []
    return list(
        (
            await session.scalars(
                select(MediaAsset)
                .where(MediaAsset.id.in_(ordered_ids))
                .order_by(MediaAsset.id)
                .with_for_update()
            )
        ).all()
    )


async def lock_media_owner(session: AsyncSession, user_id: UUID) -> None:
    """Serialize media creation with account deletion for one owner."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"media-upload:{user_id}"},
    )
