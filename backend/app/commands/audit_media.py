"""Bounded, read-only-by-default media reconciliation.

Run with ``python -m app.commands.audit_media --limit 500``. The optional
``--enqueue-confirmed`` only queues confirmed DB orphans for the guarded
deletion worker; it never removes an object directly.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from uuid import UUID

from sqlalchemy import select

from ..db.session import SessionLocal
from ..models import Listing, ListingImage, MediaAsset, User
from ..models.storage_deletion import StorageDeletionJob
from ..services.storage_deletions import enqueue_storage_deletion
from ..storage import get_storage


def classify_asset(*, referenced: bool, object_exists: bool, pending: bool, deleted: bool) -> str:
    if referenced:
        return "LIVE_REFERENCED" if object_exists else "DB_REFERENCE_MISSING_OBJECT"
    if pending:
        return "PENDING_DELETE"
    if deleted and object_exists:
        return "ORPHAN_CONFIRMED"
    return "UNKNOWN"


async def audit(limit: int, enqueue_confirmed: bool, after: UUID | None = None) -> dict[str, int]:
    summary: dict[str, int] = {}
    async with SessionLocal() as session:
        query = select(MediaAsset.id, MediaAsset.storage_key, MediaAsset.deleted_at)
        if after is not None:
            query = query.where(MediaAsset.id > after)
        assets = (await session.execute(query.order_by(MediaAsset.id).limit(limit))).all()
        ids = [asset.id for asset in assets]
        image_ids = set((await session.scalars(select(ListingImage.media_asset_id).where(ListingImage.media_asset_id.in_(ids)))).all())
        video_ids = set((await session.scalars(select(Listing.video_asset_id).where(Listing.video_asset_id.in_(ids)))).all())
        avatar_ids = set((await session.scalars(select(User.avatar_asset_id).where(User.avatar_asset_id.in_(ids)))).all())
        queued = set((await session.scalars(select(StorageDeletionJob.storage_key).where(
            StorageDeletionJob.storage_key.in_([asset.storage_key for asset in assets])
        ))).all())
        await session.commit()
        storage = get_storage()
        for asset in assets:
            try:
                exists = await asyncio.to_thread(storage.get_range, asset.storage_key, 0, 0) is not None
                kind = classify_asset(
                    referenced=asset.id in image_ids or asset.id in video_ids or asset.id in avatar_ids,
                    object_exists=exists, pending=asset.storage_key in queued,
                    deleted=asset.deleted_at is not None,
                )
            except Exception:  # noqa: BLE001 - an unknown storage failure must never authorize deletion
                kind = "UNKNOWN"
            summary[kind] = summary.get(kind, 0) + 1
            print(json.dumps({"classification": kind, "assetId": str(asset.id), "storageKey": asset.storage_key}))
            if enqueue_confirmed and kind == "ORPHAN_CONFIRMED":
                await enqueue_storage_deletion(session, asset.storage_key)
        if enqueue_confirmed:
            await session.commit()
    print(json.dumps({"summary": summary, "dryRun": not enqueue_confirmed, "nextAfter": str(assets[-1].id) if assets else None}))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--after", type=UUID)
    parser.add_argument("--enqueue-confirmed", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.limit <= 10_000:
        parser.error("--limit must be 1..10000")
    asyncio.run(audit(args.limit, args.enqueue_confirmed, args.after))


if __name__ == "__main__":
    main()
