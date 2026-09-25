from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Listing, ListingImage, MediaAsset

# The upload request has already finished object-storage work before listing
# mutation. Serializing this short DB-only section closes the race where two
# concurrent publications could both pass the duplicate check.
DUPLICATE_GUARD_LOCK_KEY = 11223320260925
ACTIVE_DUPLICATE_STATUSES = ("published", "pending", "hidden")
PHASH_MATCH_DISTANCE = 4
PHASH_ANCHOR_DISTANCE = 1
GALLERY_DICE_THRESHOLD = 0.90


@dataclass(frozen=True)
class ImageFingerprint:
    asset_id: UUID
    checksum: str
    perceptual_hash: str | None
    width: int
    height: int


def hamming_distance(left: str, right: str) -> int:
    try:
        return (int(left, 16) ^ int(right, 16)).bit_count()
    except ValueError:
        return 65


def phash_neighbors(value: str, *, distance: int = PHASH_ANCHOR_DISTANCE) -> set[str]:
    """Return a bounded full-hash neighborhood for in-memory callers."""
    try:
        number = int(value, 16)
    except ValueError:
        return {value}
    result = {f"{number:016x}"}
    if distance >= 1:
        result.update(f"{number ^ (1 << bit):016x}" for bit in range(64))
    return result


def phash_band_neighbors(value: str) -> tuple[set[str], set[str], set[str], set[str]]:
    """Return each 16-bit band plus all one-bit neighbors.

    With a 64-bit Hamming threshold of four, at least one of four 16-bit bands
    differs by no more than one bit. Expression indexes on these bands let
    PostgreSQL discover every visual candidate without scanning all media.
    """
    normalized = value.casefold().zfill(16)
    if len(normalized) != 16:
        return (set(), set(), set(), set())
    bands: list[set[str]] = []
    try:
        for start in (0, 4, 8, 12):
            number = int(normalized[start : start + 4], 16)
            neighbors = {f"{number:04x}"}
            neighbors.update(f"{number ^ (1 << bit):04x}" for bit in range(16))
            bands.append(neighbors)
    except ValueError:
        return (set(), set(), set(), set())
    return bands[0], bands[1], bands[2], bands[3]


def _phash_band_predicates(hashes: set[str]):
    band_values: list[set[str]] = [set(), set(), set(), set()]
    for value in hashes:
        for index, neighbors in enumerate(phash_band_neighbors(value)):
            band_values[index].update(neighbors)
    return [
        func.substr(MediaAsset.perceptual_hash, offset, 4).in_(values)
        for offset, values in zip((1, 5, 9, 13), band_values, strict=True)
        if values
    ]


def _aspect_ratio_close(left: ImageFingerprint, right: ImageFingerprint) -> bool:
    if min(left.width, left.height, right.width, right.height) <= 0:
        return True
    left_ratio = left.width / left.height
    right_ratio = right.width / right.height
    return abs(left_ratio - right_ratio) / max(left_ratio, right_ratio) <= 0.04


def fingerprints_match(left: ImageFingerprint, right: ImageFingerprint) -> bool:
    if left.checksum and left.checksum == right.checksum:
        return True
    if not left.perceptual_hash or not right.perceptual_hash:
        return False
    return (
        _aspect_ratio_close(left, right)
        and hamming_distance(left.perceptual_hash, right.perceptual_hash) <= PHASH_MATCH_DISTANCE
    )


def _maximum_gallery_matches(left: list[ImageFingerprint], right: list[ImageFingerprint]) -> int:
    adjacency = [
        [right_index for right_index, right_item in enumerate(right) if fingerprints_match(left_item, right_item)]
        for left_item in left
    ]
    assigned: dict[int, int] = {}

    def augment(left_index: int, seen: set[int]) -> bool:
        for right_index in adjacency[left_index]:
            if right_index in seen:
                continue
            seen.add(right_index)
            previous = assigned.get(right_index)
            if previous is None or augment(previous, seen):
                assigned[right_index] = left_index
                return True
        return False

    return sum(augment(left_index, set()) for left_index in range(len(left)))


def galleries_are_duplicates(left: list[ImageFingerprint], right: list[ImageFingerprint]) -> bool:
    """Conservatively decide whether two listing galleries are the same.

    A one-photo listing is too ambiguous for perceptual similarity, so it is a
    duplicate only when both listings contain one byte-normalized identical
    image. Multi-photo galleries need at least two one-to-one matches and a
    0.90 Sørensen-Dice score. This deliberately allows two rooms at one
    property to reuse common kitchen/building photos when their room galleries
    are materially different.
    """
    if not left or not right:
        return False
    if len(left) == len(right) == 1:
        return bool(left[0].checksum and left[0].checksum == right[0].checksum)
    if min(len(left), len(right)) < 2:
        return False
    matches = _maximum_gallery_matches(left, right)
    if matches < 2:
        return False
    return (2 * matches) / (len(left) + len(right)) >= GALLERY_DICE_THRESHOLD


def hash_galleries_are_duplicates(left: list[str], right: list[str]) -> bool:
    """Photo-only comparison for remote importer samples without local checksums."""
    left = list(dict.fromkeys(value for value in left if value))
    right = list(dict.fromkeys(value for value in right if value))
    if not left or not right:
        return False
    if len(left) == len(right) == 1:
        return left[0] == right[0]

    adjacency = [
        [
            right_index
            for right_index, right_hash in enumerate(right)
            if hamming_distance(left_hash, right_hash) <= PHASH_MATCH_DISTANCE
        ]
        for left_hash in left
    ]
    assigned: dict[int, int] = {}

    def augment(left_index: int, seen: set[int]) -> bool:
        for right_index in adjacency[left_index]:
            if right_index in seen:
                continue
            seen.add(right_index)
            previous = assigned.get(right_index)
            if previous is None or augment(previous, seen):
                assigned[right_index] = left_index
                return True
        return False

    matches = sum(augment(left_index, set()) for left_index in range(len(left)))
    return matches >= 2 and (2 * matches) / (len(left) + len(right)) >= GALLERY_DICE_THRESHOLD


def fingerprints_from_assets(assets: list[MediaAsset]) -> list[ImageFingerprint]:
    return [
        ImageFingerprint(
            asset_id=asset.id,
            checksum=asset.checksum,
            perceptual_hash=asset.perceptual_hash,
            width=asset.width,
            height=asset.height,
        )
        for asset in assets
    ]


async def listing_gallery(session: AsyncSession, listing_id: UUID) -> list[ImageFingerprint]:
    rows = (
        await session.execute(
            select(MediaAsset)
            .join(ListingImage, ListingImage.media_asset_id == MediaAsset.id)
            .where(
                ListingImage.listing_id == listing_id,
                MediaAsset.deleted_at.is_(None),
            )
            .order_by(ListingImage.sort_order)
        )
    ).scalars().all()
    return fingerprints_from_assets(list(rows))


async def _candidate_listing_ids(
    session: AsyncSession,
    fingerprints: list[ImageFingerprint],
    *,
    exclude_listing_id: UUID | None,
    external_only: bool | None = None,
) -> list[UUID]:
    checksums = {item.checksum for item in fingerprints if item.checksum}
    perceptual_hashes = {item.perceptual_hash for item in fingerprints if item.perceptual_hash}

    if not checksums and not perceptual_hashes:
        return []

    predicates = []
    if checksums:
        predicates.append(MediaAsset.checksum.in_(checksums))
    predicates.extend(_phash_band_predicates(perceptual_hashes))

    query = (
        select(ListingImage.listing_id)
        .join(MediaAsset, MediaAsset.id == ListingImage.media_asset_id)
        .join(Listing, Listing.id == ListingImage.listing_id)
        .where(
            Listing.deleted_at.is_(None),
            Listing.status.in_(ACTIVE_DUPLICATE_STATUSES),
            MediaAsset.deleted_at.is_(None),
            or_(*predicates),
        )
        .distinct()
    )
    if exclude_listing_id is not None:
        query = query.where(Listing.id != exclude_listing_id)
    if external_only is not None:
        query = query.where(Listing.is_external.is_(external_only))
    return list((await session.scalars(query)).all())


async def duplicate_listing_id(
    session: AsyncSession,
    fingerprints: list[ImageFingerprint],
    *,
    exclude_listing_id: UUID | None = None,
    external_only: bool | None = None,
) -> UUID | None:
    for candidate_id in await _candidate_listing_ids(
        session,
        fingerprints,
        exclude_listing_id=exclude_listing_id,
        external_only=external_only,
    ):
        candidate = await listing_gallery(session, candidate_id)
        if galleries_are_duplicates(fingerprints, candidate):
            return candidate_id
    return None


async def duplicate_listing_for_hashes(
    session: AsyncSession,
    hashes: list[str],
    *,
    exclude_listing_id: UUID | None = None,
    external_only: bool | None = None,
) -> UUID | None:
    hashes = list(dict.fromkeys(value for value in hashes if value))
    if not hashes:
        return None
    band_predicates = _phash_band_predicates(set(hashes))
    if not band_predicates:
        return None

    query = (
        select(ListingImage.listing_id)
        .join(MediaAsset, MediaAsset.id == ListingImage.media_asset_id)
        .join(Listing, Listing.id == ListingImage.listing_id)
        .where(
            Listing.deleted_at.is_(None),
            Listing.status.in_(ACTIVE_DUPLICATE_STATUSES),
            MediaAsset.deleted_at.is_(None),
            or_(*band_predicates),
        )
        .distinct()
    )
    if exclude_listing_id is not None:
        query = query.where(Listing.id != exclude_listing_id)
    if external_only is not None:
        query = query.where(Listing.is_external.is_(external_only))

    for candidate_id in (await session.scalars(query)).all():
        candidate_hashes = list(
            (
                await session.scalars(
                    select(MediaAsset.perceptual_hash)
                    .join(ListingImage, ListingImage.media_asset_id == MediaAsset.id)
                    .where(
                        ListingImage.listing_id == candidate_id,
                        MediaAsset.deleted_at.is_(None),
                        MediaAsset.perceptual_hash.is_not(None),
                    )
                    .order_by(ListingImage.sort_order)
                )
            ).all()
        )
        if hash_galleries_are_duplicates(hashes, [value for value in candidate_hashes if value]):
            return candidate_id
    return None


async def acquire_duplicate_guard(session: AsyncSession) -> None:
    await session.execute(select(func.pg_advisory_xact_lock(DUPLICATE_GUARD_LOCK_KEY)))


async def assert_existing_listing_gallery_is_unique(
    session: AsyncSession,
    listing_id: UUID,
) -> None:
    fingerprints = await listing_gallery(session, listing_id)
    if not fingerprints:
        return
    await acquire_duplicate_guard(session)
    duplicate_id = await duplicate_listing_id(
        session,
        fingerprints,
        exclude_listing_id=listing_id,
    )
    if duplicate_id is None:
        return
    raise HTTPException(
        409,
        detail={
            "code": "DUPLICATE_LISTING_IMAGES",
            "message": "An active listing with the same photo gallery already exists.",
            "fieldErrors": {
                "assetIds": "Estas fotografías ya pertenecen a un anuncio activo o prácticamente idéntico."
            },
        },
    )


async def assert_gallery_is_unique(
    session: AsyncSession,
    listing_id: UUID,
    assets: list[MediaAsset],
) -> None:
    fingerprints = fingerprints_from_assets(assets)
    if not fingerprints:
        return

    await acquire_duplicate_guard(session)
    duplicate_id = await duplicate_listing_id(
        session,
        fingerprints,
        exclude_listing_id=listing_id,
    )
    if duplicate_id is None:
        return

    raise HTTPException(
        409,
        detail={
            "code": "DUPLICATE_LISTING_IMAGES",
            "message": "An active listing with the same photo gallery already exists.",
            "fieldErrors": {
                "assetIds": "Estas fotografías ya pertenecen a un anuncio activo o prácticamente idéntico."
            },
        },
    )


def external_gallery_is_reconciled(
    *,
    is_external: bool,
    external_image_urls: list[str],
    stored_image_count: int,
) -> bool:
    if not is_external:
        return True
    expected_count = len(list(dict.fromkeys(external_image_urls))[:20])
    return expected_count > 0 and stored_image_count == expected_count


async def all_active_galleries(session: AsyncSession) -> dict[UUID, list[ImageFingerprint]]:
    rows = (
        await session.execute(
            select(
                ListingImage.listing_id,
                MediaAsset,
                Listing.is_external,
                Listing.external_image_urls,
            )
            .join(MediaAsset, MediaAsset.id == ListingImage.media_asset_id)
            .join(Listing, Listing.id == ListingImage.listing_id)
            .where(
                Listing.deleted_at.is_(None),
                Listing.status.in_(ACTIVE_DUPLICATE_STATUSES),
                MediaAsset.deleted_at.is_(None),
            )
            .order_by(ListingImage.listing_id, ListingImage.sort_order)
        )
    ).all()
    galleries: dict[UUID, list[ImageFingerprint]] = defaultdict(list)
    external_state: dict[UUID, tuple[bool, list[str]]] = {}
    for listing_id, asset, is_external, external_image_urls in rows:
        galleries[listing_id].append(
            ImageFingerprint(
                asset_id=asset.id,
                checksum=asset.checksum,
                perceptual_hash=asset.perceptual_hash,
                width=asset.width,
                height=asset.height,
            )
        )
        external_state[listing_id] = (bool(is_external), list(external_image_urls or []))

    return {
        listing_id: gallery
        for listing_id, gallery in galleries.items()
        if external_gallery_is_reconciled(
            is_external=external_state[listing_id][0],
            external_image_urls=external_state[listing_id][1],
            stored_image_count=len(gallery),
        )
    }
