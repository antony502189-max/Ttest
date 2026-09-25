from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import DiscardedListing, Favorite, Listing, ListingImage, MediaAsset
from ..storage import get_storage
from .catalog import touch_catalog
from .listing_deduplication import (
    acquire_duplicate_guard,
    all_active_galleries,
    galleries_are_duplicates,
    phash_band_neighbors,
)
from .media_processing import perceptual_hash


async def backfill_active_listing_hashes(session: AsyncSession) -> int:
    """Populate missing perceptual hashes without holding a DB transaction over storage I/O."""
    rows = (
        await session.execute(
            select(MediaAsset.id, MediaAsset.storage_key)
            .join(ListingImage, ListingImage.media_asset_id == MediaAsset.id)
            .join(Listing, Listing.id == ListingImage.listing_id)
            .where(
                Listing.deleted_at.is_(None),
                Listing.status.in_(("published", "pending", "hidden")),
                MediaAsset.deleted_at.is_(None),
                MediaAsset.perceptual_hash.is_(None),
            )
            .distinct()
        )
    ).all()
    await session.commit()

    storage = get_storage()
    updated = 0
    for asset_id, storage_key in rows:
        content = await asyncio.to_thread(storage.get, storage_key)
        if content is None:
            continue
        value = await asyncio.to_thread(perceptual_hash, content)
        asset = await session.get(MediaAsset, asset_id)
        if asset is None or asset.deleted_at is not None or asset.perceptual_hash is not None:
            await session.rollback()
            continue
        asset.perceptual_hash = value
        await session.commit()
        updated += 1
    return updated


def _candidate_pairs(galleries):
    checksum_index: dict[str, set[UUID]] = defaultdict(set)
    phash_band_index: dict[tuple[int, str], set[UUID]] = defaultdict(set)
    pairs: set[tuple[UUID, UUID]] = set()

    for listing_id, gallery in galleries.items():
        for image in gallery:
            if image.checksum:
                for other in checksum_index[image.checksum]:
                    pairs.add(tuple(sorted((listing_id, other), key=str)))
                checksum_index[image.checksum].add(listing_id)
            if image.perceptual_hash:
                bands = phash_band_neighbors(image.perceptual_hash)
                for band_index, neighbors in enumerate(bands):
                    for neighbor in neighbors:
                        for other in phash_band_index.get((band_index, neighbor), ()):
                            pairs.add(tuple(sorted((listing_id, other), key=str)))
                normalized = image.perceptual_hash.casefold().zfill(16)
                for band_index, start in enumerate((0, 4, 8, 12)):
                    phash_band_index[(band_index, normalized[start : start + 4])].add(listing_id)
    return pairs


def _duplicate_groups(galleries) -> list[set[UUID]]:
    parent: dict[UUID, UUID] = {listing_id: listing_id for listing_id in galleries}

    def find(value: UUID) -> UUID:
        root = value
        while parent[root] != root:
            root = parent[root]
        while parent[value] != value:
            next_value = parent[value]
            parent[value] = root
            value = next_value
        return root

    def union(left: UUID, right: UUID) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left_id, right_id in _candidate_pairs(galleries):
        if galleries_are_duplicates(galleries[left_id], galleries[right_id]):
            union(left_id, right_id)

    groups: dict[UUID, set[UUID]] = defaultdict(set)
    for listing_id in galleries:
        groups[find(listing_id)].add(listing_id)
    return [group for group in groups.values() if len(group) > 1]


def _canonical_key(listing: Listing) -> tuple:
    # Prefer a user's own listing over a parser card, then keep the oldest
    # durable public identity to minimize broken bookmarks.
    published = listing.published_at or listing.created_at
    return (listing.is_external, published, str(listing.id))


async def _move_scoped_state(
    session: AsyncSession,
    model,
    loser_id: UUID,
    canonical_id: UUID,
) -> None:
    user_ids = list((await session.scalars(select(model.user_id).where(model.listing_id == loser_id))).all())
    if user_ids:
        await session.execute(
            insert(model)
            .values([{"user_id": user_id, "listing_id": canonical_id} for user_id in user_ids])
            .on_conflict_do_nothing(index_elements=["user_id", "listing_id"])
        )
        await session.execute(delete(model).where(model.listing_id == loser_id))


async def deduplicate_active_listings(session: AsyncSession, *, apply: bool) -> dict:
    if apply:
        # Manual invocations may run while the application is live. Share the
        # same transaction-level guard as create/update/import so the cleanup
        # snapshot cannot race a newly published gallery.
        await acquire_duplicate_guard(session)
    galleries = await all_active_galleries(session)
    groups = _duplicate_groups(galleries)
    if not groups:
        return {"groups": [], "duplicates": 0, "changed": 0}

    listing_ids = {listing_id for group in groups for listing_id in group}
    listings = {
        listing.id: listing
        for listing in (
            await session.scalars(
                select(Listing).where(Listing.id.in_(listing_ids)).with_for_update()
            )
        ).all()
    }

    report_groups: list[dict[str, object]] = []
    duplicate_count = 0
    changed = 0
    for group in groups:
        available = [listings[listing_id] for listing_id in group if listing_id in listings]
        if len(available) < 2:
            continue
        canonical = min(available, key=_canonical_key)
        losers = [listing for listing in available if listing.id != canonical.id]
        duplicate_count += len(losers)
        report_groups.append(
            {
                "canonical": str(canonical.id),
                "canonicalExternal": canonical.is_external,
                "duplicates": [str(listing.id) for listing in losers],
            }
        )
        if not apply:
            continue
        for loser in losers:
            await _move_scoped_state(session, Favorite, loser.id, canonical.id)
            await _move_scoped_state(session, DiscardedListing, loser.id, canonical.id)
            loser.status = "closed"
            loser.closed_reason = "duplicate"
            loser.last_synced_at = datetime.now(UTC)
            changed += 1

    if apply and changed:
        await touch_catalog(session)
        await session.commit()
    else:
        await session.rollback()

    return {
        "groups": report_groups,
        "duplicates": duplicate_count,
        "changed": changed,
    }
