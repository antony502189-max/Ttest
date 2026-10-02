from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.media_limits import MAX_LISTING_PHOTOS, MIN_LISTING_PHOTOS
from ..models import Listing, ListingImage, MediaAsset
from .catalog import touch_catalog
from .listing_deduplication import acquire_duplicate_guard

ACTIVE_INTERNAL_STATUSES = ("published", "pending", "hidden")


@dataclass(frozen=True)
class GalleryImageSnapshot:
    asset_id: UUID
    checksum: str
    sort_order: int
    is_cover: bool


@dataclass(frozen=True)
class GalleryListingSnapshot:
    listing_id: UUID
    owner_id: UUID
    title: str
    street: str | None
    postcode: str | None
    rental_mode: str
    status: str
    images: tuple[GalleryImageSnapshot, ...]


def _normalized_text(value: str | None) -> str:
    decomposed = unicodedata.normalize("NFKD", (value or "").strip().casefold())
    return " ".join(
        "".join(char for char in decomposed if not unicodedata.combining(char)).split()
    )


def _address_key(snapshot: GalleryListingSnapshot) -> tuple[str, str] | None:
    street = _normalized_text(snapshot.street)
    postcode = "".join((snapshot.postcode or "").strip().casefold().split())
    return (street, postcode) if street and postcode else None


def _matching_repair_candidates(
    target: GalleryListingSnapshot,
    candidates: list[GalleryListingSnapshot],
) -> list[GalleryListingSnapshot]:
    """Return only siblings that can restore a truncated gallery without guessing.

    A safe candidate must belong to the same owner and normalized private
    address, have the same normalized title, contain a valid full gallery, and
    start with the exact normalized-image checksum sequence already stored on
    the target. This supports legacy 1-4 photo truncation while refusing a
    merely similar room/gallery.
    """
    if not 1 <= len(target.images) < MIN_LISTING_PHOTOS:
        return []
    target_address = _address_key(target)
    if target_address is None:
        return []
    target_checksums = [image.checksum for image in target.images]
    result: list[GalleryListingSnapshot] = []
    for candidate in candidates:
        if candidate.listing_id == target.listing_id or candidate.owner_id != target.owner_id:
            continue
        if _address_key(candidate) != target_address:
            continue
        if _normalized_text(candidate.title) != _normalized_text(target.title):
            continue
        if not MIN_LISTING_PHOTOS <= len(candidate.images) <= MAX_LISTING_PHOTOS:
            continue
        candidate_checksums = [image.checksum for image in candidate.images]
        if candidate_checksums[: len(target_checksums)] != target_checksums:
            continue
        result.append(candidate)
    return result


async def active_listing_photo_count(session: AsyncSession, listing_id: UUID) -> int:
    return int(
        await session.scalar(
            select(func.count(MediaAsset.id))
            .select_from(ListingImage)
            .join(
                MediaAsset,
                and_(
                    MediaAsset.id == ListingImage.media_asset_id,
                    MediaAsset.deleted_at.is_(None),
                ),
            )
            .where(ListingImage.listing_id == listing_id)
        )
        or 0
    )


async def assert_existing_listing_photo_count(session: AsyncSession, listing_id: UUID) -> None:
    listing = await session.get(Listing, listing_id)
    if listing is None or listing.is_external:
        return
    count = await active_listing_photo_count(session, listing_id)
    if MIN_LISTING_PHOTOS <= count <= MAX_LISTING_PHOTOS:
        return
    raise HTTPException(
        409,
        detail={
            "code": "LISTING_PHOTO_COUNT_INVALID",
            "message": (
                f"This listing has {count} active photos; "
                f"{MIN_LISTING_PHOTOS} to {MAX_LISTING_PHOTOS} are required before publication."
            ),
            "fieldErrors": {
                "assetIds": (
                    f"Restore or upload {MIN_LISTING_PHOTOS} to "
                    f"{MAX_LISTING_PHOTOS} photos before publishing."
                )
            },
        },
    )


async def _snapshot(session: AsyncSession, listing: Listing) -> GalleryListingSnapshot:
    rows = (
        await session.execute(
            select(ListingImage, MediaAsset)
            .join(MediaAsset, MediaAsset.id == ListingImage.media_asset_id)
            .where(
                ListingImage.listing_id == listing.id,
                MediaAsset.deleted_at.is_(None),
            )
            .order_by(ListingImage.sort_order)
        )
    ).all()
    return GalleryListingSnapshot(
        listing_id=listing.id,
        owner_id=listing.owner_user_id,
        title=listing.title,
        street=listing.street,
        postcode=listing.postcode,
        rental_mode=listing.rental_mode,
        status=listing.status,
        images=tuple(
            GalleryImageSnapshot(
                asset_id=asset.id,
                checksum=asset.checksum,
                sort_order=image.sort_order,
                is_cover=image.is_cover,
            )
            for image, asset in rows
        ),
    )


async def repair_legacy_internal_galleries(session: AsyncSession, *, apply: bool) -> dict:
    """Audit and optionally repair unambiguous legacy internal gallery truncation.

    The routine never invents media and never copies from a merely similar
    listing. It only appends the missing suffix from exactly one full sibling
    whose owner, normalized private address, title and existing checksum prefix
    all match the truncated target.
    """
    if apply:
        await acquire_duplicate_guard(session)

    count_rows = (
        await session.execute(
            select(
                Listing.id,
                func.count(MediaAsset.id).label("photo_count"),
            )
            .select_from(Listing)
            .outerjoin(ListingImage, ListingImage.listing_id == Listing.id)
            .outerjoin(
                MediaAsset,
                and_(
                    MediaAsset.id == ListingImage.media_asset_id,
                    MediaAsset.deleted_at.is_(None),
                ),
            )
            .where(
                Listing.deleted_at.is_(None),
                Listing.is_external.is_(False),
                Listing.status.in_(ACTIVE_INTERNAL_STATUSES),
            )
            .group_by(Listing.id)
            .having(func.count(MediaAsset.id) < MIN_LISTING_PHOTOS)
        )
    ).all()

    repairs: list[dict[str, object]] = []
    unresolved: list[dict[str, object]] = []

    for target_id, observed_count in count_rows:
        target_listing = await session.scalar(
            select(Listing).where(Listing.id == target_id).with_for_update()
        ) if apply else await session.get(Listing, target_id)
        if target_listing is None:
            continue
        target = await _snapshot(session, target_listing)

        if not target.images:
            unresolved.append({
                "listingId": str(target.listing_id),
                "photoCount": 0,
                "reason": "no-active-cover",
            })
            continue

        siblings = list(
            (
                await session.scalars(
                    select(Listing).where(
                        Listing.owner_user_id == target.owner_id,
                        Listing.id != target.listing_id,
                        Listing.deleted_at.is_(None),
                        Listing.is_external.is_(False),
                        Listing.status.in_(ACTIVE_INTERNAL_STATUSES),
                    )
                )
            ).all()
        )
        candidate_snapshots = [await _snapshot(session, sibling) for sibling in siblings]
        candidates = _matching_repair_candidates(target, candidate_snapshots)

        if len(candidates) != 1:
            unresolved.append({
                "listingId": str(target.listing_id),
                "photoCount": len(target.images),
                "reason": "ambiguous-candidate" if len(candidates) > 1 else "no-exact-candidate",
                "candidateIds": [str(candidate.listing_id) for candidate in candidates],
            })
            continue

        source = candidates[0]
        if apply:
            # Revalidate the exact checksum prefix under row locks before
            # mutating, so a live manual invocation cannot copy stale state.
            source_listing = await session.scalar(
                select(Listing).where(Listing.id == source.listing_id).with_for_update()
            )
            if source_listing is None:
                unresolved.append({
                    "listingId": str(target.listing_id),
                    "photoCount": len(target.images),
                    "reason": "source-disappeared",
                })
                continue
            locked_target = await _snapshot(session, target_listing)
            locked_source = await _snapshot(session, source_listing)
            if _matching_repair_candidates(locked_target, [locked_source]) != [locked_source]:
                unresolved.append({
                    "listingId": str(target.listing_id),
                    "photoCount": len(locked_target.images),
                    "reason": "state-changed",
                })
                continue

            existing_count = len(locked_target.images)
            for source_image in locked_source.images[existing_count:]:
                session.add(
                    ListingImage(
                        listing_id=locked_target.listing_id,
                        media_asset_id=source_image.asset_id,
                        sort_order=source_image.sort_order,
                        is_cover=False,
                    )
                )
            await session.flush()
            final_count = await active_listing_photo_count(session, locked_target.listing_id)
            if final_count != len(locked_source.images):
                raise RuntimeError(
                    f"gallery repair count mismatch for {locked_target.listing_id}: "
                    f"{final_count} != {len(locked_source.images)}"
                )

        repairs.append({
            "listingId": str(target.listing_id),
            "sourceListingId": str(source.listing_id),
            "before": int(observed_count),
            "after": len(source.images),
            "targetRentalMode": target.rental_mode,
            "sourceRentalMode": source.rental_mode,
        })

    if apply and repairs:
        await touch_catalog(session)
        await session.commit()
    else:
        await session.rollback()

    return {
        "mode": "apply" if apply else "dry-run",
        "scanned": len(count_rows),
        "repairable": len(repairs),
        "repaired": len(repairs) if apply else 0,
        "repairs": repairs,
        "unresolved": unresolved,
    }
