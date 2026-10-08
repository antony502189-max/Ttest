from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from time import perf_counter
from uuid import UUID, uuid4

import httpx
from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]
from fastapi import HTTPException
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..core.media_keys import variant_storage_key
from ..core.media_limits import MAX_LISTING_PHOTOS
from ..core.observability import EXTERNAL_IMPORT_DURATION, EXTERNAL_IMPORTS
from ..external_sources import (
    DiscoveryResult,
    ExternalListingSource,
    NormalizedListing,
    SourceBlocked,
    is_in_import_scope,
    parse_optional_date,
    parse_optional_datetime,
)
from ..models import ExternalImportRun, Listing, ListingImage, MediaAsset, User
from ..models import ExternalListingSource as SourceRecord
from ..models.room_details import ListingRoomDetails
from ..rental_classification import ROOM_TYPES, property_type
from ..repositories.listings import point
from ..storage import get_storage
from .catalog import touch_catalog
from .listing_deduplication import (
    ACTIVE_DUPLICATE_STATUSES,
    ExternalDuplicateMetadata,
    ImageFingerprint,
    acquire_duplicate_guard,
    duplicate_listing_id,
    external_gallery_is_reconciled,
    listing_gallery,
    listing_gallery_is_reconciled,
    same_source_external_duplicates,
)
from .media_processing import perceptual_hash, prepare_image, validate_and_normalize
from .notifications import notify_favorited_listing_unavailable, notify_saved_search_matches
from .storage_deletions import enqueue_storage_deletions

logger = logging.getLogger(__name__)
SYSTEM_EMAIL = "external-import@112233.es"


def require_no_active_transaction(session: AsyncSession, operation: str) -> None:
    """Fail closed if a future refactor puts remote I/O inside a DB transaction."""
    if session.in_transaction():
        raise RuntimeError(f"Database transaction must be closed before {operation}")


class SourceRunCounters(dict[str, int]):
    """Counters plus the terminal state for the worker's aggregate health."""

    result: str = "failed"


def completed_source_contract(counters: dict[str, int]) -> bool:
    """Require at least one valid rental detail and a publishable outcome."""
    reached_valid_detail = all(
        counters.get(key, 0) > 0
        for key in ("discovered_urls", "fetched_details")
    )
    reached_valid_detail = reached_valid_detail and counters.get("accepted_rentals", counters.get("accepted_rooms", 0)) > 0
    publishable = any(
        counters.get(key, 0) > 0
        for key in ("imported", "updated", "unchanged", "restored")
    )
    return reached_valid_detail and publishable


def public_location(item: NormalizedListing) -> tuple[float, float] | None:
    """Return only a point explicitly published by the external source."""
    if item.latitude is None or item.longitude is None:
        return None
    return item.latitude, item.longitude


def similarity(left: str, right: str) -> float:
    def tokens(value: str) -> set[str]:
        decomposed = unicodedata.normalize("NFKD", value.casefold())
        normalized = "".join(char for char in decomposed if not unicodedata.combining(char))
        return {token for token in re.findall(r"\w+", normalized) if len(token) > 2}

    left_tokens, right_tokens = tokens(left), tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def completeness_score(item: NormalizedListing) -> int:
    return sum(
        bool(value)
        for value in (
            item.description,
            item.phone,
            item.whatsapp,
            item.email,
            item.latitude is not None and item.longitude is not None,
        )
    ) + min(len(item.photos), 10)


def listing_completeness_score(listing: Listing) -> int:
    return sum(
        bool(value)
        for value in (
            listing.description,
            listing.external_contact_phone,
            listing.external_contact_whatsapp,
            listing.external_contact_email,
            listing.primary_source_url,
        )
    ) + min(len(listing.external_image_urls), 10)


async def public_image_fingerprints(urls: list[str]) -> list[ImageFingerprint]:
    """Sample the complete bounded source gallery or decline deduplication.

    A partial sample is unsafe for room listings because several rooms in one
    dwelling may share the same first kitchen/building photos. Cross-source
    identity is therefore established only when every unique source image in
    the bounded 15-photo gallery can be inspected successfully.
    """
    source_urls = list(dict.fromkeys(urls))[:MAX_LISTING_PHOTOS]
    if not source_urls:
        return []

    settings = get_settings()
    semaphore = asyncio.Semaphore(max(1, min(settings.external_import_max_concurrency_per_source, 4)))

    async with httpx.AsyncClient(
        timeout=settings.external_import_request_timeout_seconds,
        follow_redirects=True,
    ) as client:

        async def sample(index: int, url: str) -> ImageFingerprint | None:
            async with semaphore:
                try:
                    response = await client.get(
                        url,
                        headers={"User-Agent": settings.external_import_user_agent},
                    )
                    content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                    if (
                        response.status_code != 200
                        or not content_type.startswith("image/")
                        or len(response.content) > settings.max_upload_bytes
                    ):
                        return None
                    normalized, width, height = await asyncio.to_thread(
                        validate_and_normalize,
                        response.content,
                    )
                    return ImageFingerprint(
                        asset_id=UUID(int=index + 1),
                        checksum=hashlib.sha256(normalized).hexdigest(),
                        perceptual_hash=await asyncio.to_thread(perceptual_hash, normalized),
                        width=width,
                        height=height,
                    )
                except (HTTPException, OSError, ValueError, httpx.HTTPError):
                    return None

        sampled = await asyncio.gather(
            *(sample(index, url) for index, url in enumerate(source_urls))
        )

    result: list[ImageFingerprint] = []
    for fingerprint in sampled:
        if fingerprint is None:
            return []
        result.append(fingerprint)
    return result


def external_storage_key(owner_id: UUID, asset_id: UUID) -> str:
    """Return a collision-free key so one failed concurrent insert cannot delete another asset."""
    return f"external/{owner_id}/{asset_id}.webp"


@dataclass(frozen=True)
class PreparedExternalImage:
    content: bytes
    width: int
    height: int
    checksum: str
    perceptual_hash: str
    variants: dict[str, bytes] = field(default_factory=dict)


async def download_external_image(client: httpx.AsyncClient, url: str) -> PreparedExternalImage | None:
    response = await client.get(url, headers={"User-Agent": get_settings().external_import_user_agent})
    content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
    if (
        response.status_code != 200
        or not content_type.startswith("image/")
        or len(response.content) > get_settings().max_upload_bytes
    ):
        return None
    prepared = await asyncio.to_thread(prepare_image, response.content)
    return PreparedExternalImage(
        content=prepared.content,
        width=prepared.width,
        height=prepared.height,
        checksum=hashlib.sha256(prepared.content).hexdigest(),
        perceptual_hash=prepared.perceptual_hash,
        variants=prepared.variants,
    )


async def _delete_external_objects(storage, storage_keys: set[str]) -> None:
    for storage_key in storage_keys:
        try:
            await asyncio.to_thread(storage.delete, storage_key)
        except (OSError, BotoCoreError, ClientError):
            logger.exception(
                "external_image_cleanup_failed",
                extra={"storage_key": storage_key},
            )


async def import_images(
    session: AsyncSession,
    listing_id: UUID,
    owner_id: UUID,
    urls: list[str],
) -> None:
    """Reconcile one imported listing to its current bounded source gallery.

    Remote/image/object-storage I/O happens with no open DB transaction. The
    relational gallery is replaced only after every unique source image in the
    bounded gallery downloads successfully, so a transient remote failure
    can never erase a previously healthy gallery. Removed source images are
    detached and truly orphaned media is queued for storage deletion.
    """
    settings = get_settings()
    await session.commit()
    # Product galleries have one hard ceiling everywhere, including imports.
    # Legacy external rows above the limit are intentionally reconciled down
    # to the first MAX_LISTING_PHOTOS source images on their next sync.
    image_cap = MAX_LISTING_PHOTOS
    source_urls = list(dict.fromkeys(urls))[:image_cap]
    if not settings.external_import_download_images or not source_urls:
        return

    storage = get_storage()
    semaphore = asyncio.Semaphore(max(1, min(settings.external_import_max_concurrency_per_source, 4)))
    async with httpx.AsyncClient(
        timeout=settings.external_import_request_timeout_seconds,
        follow_redirects=True,
    ) as client:

        async def fetch(index: int, url: str) -> tuple[int, PreparedExternalImage | None]:
            async with semaphore:
                require_no_active_transaction(session, "external image download")
                try:
                    return index, await download_external_image(client, url)
                except (HTTPException, OSError, ValueError, httpx.HTTPError):
                    logger.info(
                        "external_image_skipped",
                        extra={"listing_id": str(listing_id), "image_position": index},
                    )
                    return index, None

        downloaded = await asyncio.gather(
            *(fetch(index, url) for index, url in enumerate(source_urls))
        )

    downloaded.sort(key=lambda item: item[0])
    if any(prepared is None for _, prepared in downloaded):
        logger.info(
            "external_gallery_reconciliation_deferred",
            extra={"listing_id": str(listing_id), "requested_images": len(source_urls)},
        )
        return

    prepared_gallery: list[tuple[str, PreparedExternalImage]] = []
    seen_checksums: set[str] = set()
    for index, prepared in downloaded:
        if prepared is None or prepared.checksum in seen_checksums:
            continue
        seen_checksums.add(prepared.checksum)
        prepared_gallery.append((source_urls[index], prepared))
    if not prepared_gallery:
        return

    checksums = [prepared.checksum for _, prepared in prepared_gallery]
    existing_assets = list(
        (
            await session.scalars(
                select(MediaAsset).where(
                    MediaAsset.owner_id == owner_id,
                    MediaAsset.checksum.in_(checksums),
                    MediaAsset.kind == "listing_image",
                    MediaAsset.deleted_at.is_(None),
                )
            )
        ).all()
    )
    await session.commit()
    by_checksum = {asset.checksum: asset for asset in existing_assets}

    created_storage_keys: set[str] = set()
    created_assets: list[MediaAsset] = []
    desired_assets: list[MediaAsset] = []
    try:
        for _url, prepared in prepared_gallery:
            asset = by_checksum.get(prepared.checksum)
            if asset is not None:
                desired_assets.append(asset)
                continue

            asset_id = uuid4()
            storage_key = external_storage_key(owner_id, asset_id)
            objects = [
                (storage_key, prepared.content),
                *[
                    (variant_storage_key(storage_key, variant), variant_content)
                    for variant, variant_content in prepared.variants.items()
                ],
            ]
            require_no_active_transaction(session, "external image storage")
            storage_results = await asyncio.gather(
                *(
                    asyncio.to_thread(storage.put, object_key, object_content)
                    for object_key, object_content in objects
                ),
                return_exceptions=True,
            )
            storage_error = next(
                (result for result in storage_results if isinstance(result, Exception)),
                None,
            )
            if storage_error is not None:
                created_storage_keys.add(storage_key)
                raise OSError("External image storage write failed") from storage_error

            created_storage_keys.add(storage_key)
            asset = MediaAsset(
                id=asset_id,
                owner_id=owner_id,
                storage_key=storage_key,
                mime_type="image/webp",
                size_bytes=len(prepared.content),
                width=prepared.width,
                height=prepared.height,
                checksum=prepared.checksum,
                perceptual_hash=prepared.perceptual_hash,
                kind="listing_image",
            )
            created_assets.append(asset)
            desired_assets.append(asset)
            by_checksum[prepared.checksum] = asset

        if created_assets:
            session.add_all(created_assets)
            await session.flush()

        locked_listing = await session.scalar(
            select(Listing).where(Listing.id == listing_id).with_for_update()
        )
        if locked_listing is None:
            raise RuntimeError("Imported listing disappeared during image reconciliation")
        locked_listing.external_image_urls = [url for url, _prepared in prepared_gallery]

        current_ids = list(
            (
                await session.scalars(
                    select(ListingImage.media_asset_id)
                    .where(ListingImage.listing_id == listing_id)
                    .order_by(ListingImage.sort_order)
                    .with_for_update()
                )
            ).all()
        )
        desired_ids = [asset.id for asset in desired_assets]
        if current_ids != desired_ids:
            await session.execute(delete(ListingImage).where(ListingImage.listing_id == listing_id))
            for sort_order, asset in enumerate(desired_assets):
                session.add(
                    ListingImage(
                        listing_id=listing_id,
                        media_asset_id=asset.id,
                        sort_order=sort_order,
                        is_cover=sort_order == 0,
                    )
                )
            await session.flush()

            stale_ids = set(current_ids) - set(desired_ids)
            if stale_ids:
                stale_assets = list(
                    (
                        await session.scalars(
                            select(MediaAsset)
                            .where(
                                MediaAsset.id.in_(stale_ids),
                                MediaAsset.deleted_at.is_(None),
                            )
                            .with_for_update()
                        )
                    ).all()
                )
                still_attached = set(
                    (
                        await session.scalars(
                            select(ListingImage.media_asset_id).where(
                                ListingImage.media_asset_id.in_(stale_ids)
                            )
                        )
                    ).all()
                )
                avatar_ids = {
                    value
                    for value in (
                        await session.scalars(
                            select(User.avatar_asset_id).where(User.avatar_asset_id.in_(stale_ids))
                        )
                    ).all()
                    if value is not None
                }
                orphaned = [
                    asset
                    for asset in stale_assets
                    if asset.id not in still_attached and asset.id not in avatar_ids
                ]
                if orphaned:
                    now = datetime.now(UTC)
                    for asset in orphaned:
                        asset.deleted_at = now
                    await enqueue_storage_deletions(
                        session,
                        {asset.storage_key for asset in orphaned},
                    )
            await touch_catalog(session)

        await session.commit()
    except (OSError, BotoCoreError, ClientError, SQLAlchemyError, RuntimeError):
        await session.rollback()
        await _delete_external_objects(storage, created_storage_keys)
        logger.exception(
            "external_gallery_reconciliation_failed",
            extra={"listing_id": str(listing_id)},
        )


async def system_user(session: AsyncSession) -> User:
    user = await session.scalar(select(User).where(User.email == SYSTEM_EMAIL))
    if user:
        return user
    user = User(
        email=SYSTEM_EMAIL,
        password_hash=None,
        name="Anunciante externo",
        role="admin",
        initials="AE",
        email_verified=True,
    )
    session.add(user)
    await session.flush()
    return user


async def canonical_for(
    session: AsyncSession,
    item: NormalizedListing,
    image_fingerprints: list[ImageFingerprint],
) -> Listing | None:
    """Find an existing external canonical only from the photo gallery.

    Contact details, address/city, title, description and price are deliberately
    excluded: one advertiser or one building can legitimately contain several
    different rooms/listings. Rental mode is part of identity so the same room
    may legitimately be offered for long stay and holiday rental.
    """
    duplicate_id = await duplicate_listing_id(
        session,
        image_fingerprints,
        external_only=True,
        rental_mode=item.rental_mode,
    )
    return await session.get(Listing, duplicate_id) if duplicate_id is not None else None


def _item_duplicate_metadata(item: NormalizedListing) -> ExternalDuplicateMetadata:
    return ExternalDuplicateMetadata(
        source=item.source_name,
        rental_mode=item.rental_mode,
        title=item.title,
        description=item.description,
        city=item.city,
        area=item.area,
        address=item.public_address or item.area,
        price=item.price_amount,
        room_type=item.room_type,
        advertiser_name=item.advertiser_name,
    )


def _listing_duplicate_metadata(listing: Listing) -> ExternalDuplicateMetadata:
    price = listing.nightly_price if listing.rental_mode == "holiday" else listing.monthly_price
    return ExternalDuplicateMetadata(
        source=listing.primary_source,
        rental_mode=listing.rental_mode,
        title=listing.title,
        description=listing.description,
        city=listing.city,
        area=listing.area,
        address=listing.approximate_address,
        price=price,
        room_type=listing.room_type,
        advertiser_name=listing.advertiser_name,
    )


async def same_source_canonical_for(
    session: AsyncSession,
    item: NormalizedListing,
    image_fingerprints: list[ImageFingerprint],
) -> Listing | None:
    """Find a same-provider repost that the global 0.90 gallery rule keeps separate.

    This path is deliberately narrow: SQL first limits candidates to the same
    provider, rental mode, city and price; the final decision also requires
    exact normalized title/description/location metadata, a matching cover and
    strong gallery overlap.
    """
    if len(image_fingerprints) < 4 or not item.description:
        return None
    price_column = Listing.nightly_price if item.rental_mode == "holiday" else Listing.monthly_price
    candidates = list(
        (
            await session.scalars(
                select(Listing).where(
                    Listing.deleted_at.is_(None),
                    Listing.status.in_(ACTIVE_DUPLICATE_STATUSES),
                    Listing.is_external.is_(True),
                    Listing.primary_source == item.source_name,
                    Listing.rental_mode == item.rental_mode,
                    Listing.city == item.city,
                    price_column == item.price_amount,
                )
            )
        ).all()
    )
    item_metadata = _item_duplicate_metadata(item)
    for candidate in candidates:
        candidate_gallery = await listing_gallery(session, candidate.id)
        if not await listing_gallery_is_reconciled(
            session,
            candidate.id,
            stored_image_count=len(candidate_gallery),
        ):
            continue
        if same_source_external_duplicates(
            item_metadata,
            _listing_duplicate_metadata(candidate),
            image_fingerprints,
            candidate_gallery,
        ):
            return candidate
    return None


def normalized_snapshot(item: NormalizedListing) -> dict:
    return json.loads(json.dumps(asdict(item), default=str))


def listing_from_snapshot(payload: dict) -> NormalizedListing:
    """Restore date types after JSONB serialisation before a primary promotion."""
    value = dict(payload)
    value["available_from"] = parse_optional_date(value.get("available_from"))
    value["published_at"] = parse_optional_datetime(value.get("published_at"))
    return NormalizedListing(**value)


async def apply_primary_source_snapshot(session: AsyncSession, listing: Listing, item: NormalizedListing) -> None:
    """Apply existing primary metadata without network I/O or a transaction commit."""
    now = datetime.now(UTC)
    room_capacity = item.room_capacity if item.room_capacity is not None and 1 <= item.room_capacity <= 10 else None
    coordinates = public_location(item)
    room_details = await session.get(ListingRoomDetails, listing.id)
    if room_details is None and room_capacity is not None:
        room_details = ListingRoomDetails(listing_id=listing.id)
        session.add(room_details)
    if room_details is not None:
        room_details.room_capacity_v2 = room_capacity
    listing.title = item.title
    listing.description = item.description
    listing.home_description = item.description
    listing.city = item.city
    listing.area = item.area
    listing.approximate_address = item.public_address or item.area
    listing.rental_mode = item.rental_mode
    listing.room_type = item.room_type
    listing.bedroom_count = item.bedroom_count if item.bedroom_count else None
    listing.monthly_price = item.price_amount if item.rental_mode == "long" else None
    listing.nightly_price = item.price_amount if item.rental_mode == "holiday" else None
    listing.weekly_price = item.weekly_price_amount
    listing.minimum_stay_months = item.minimum_stay_months
    listing.minimum_nights = item.minimum_nights
    listing.deposit_amount = item.deposit_amount
    listing.deposit_text = item.deposit_text
    listing.bills_included = item.bills_included
    listing.bills_text = item.bills_text
    listing.furnished = item.furnished
    listing.bathroom = item.bathroom
    listing.kitchen = item.kitchen
    listing.room_size_m2 = item.room_size_m2
    listing.room_capacity = min(room_capacity, 2) if room_capacity is not None else None
    listing.tenant_requirement = item.tenant_requirement
    listing.pets_allowed = item.pets_allowed
    listing.children_allowed = item.children_allowed
    listing.smoking_allowed = item.smoking_allowed
    listing.empadronamiento_allowed = item.empadronamiento_allowed
    listing.amenities = item.amenities
    listing.restrictions = item.restrictions
    listing.advertiser_name = item.advertiser_name
    listing.advertiser_type = item.advertiser_type
    listing.available_from = item.available_from
    if item.published_at:
        listing.published_at = item.published_at
    if item.photos_complete or not listing.external_image_urls:
        listing.external_image_urls = item.photos
    listing.primary_source = item.source_name
    listing.primary_source_url = item.source_url
    listing.source_price_text = item.source_price_text
    listing.source_price_currency = item.price_currency
    listing.source_price_period = item.price_period
    listing.source_price_is_from = item.price_is_from
    listing.external_contact_phone = item.phone
    listing.external_contact_whatsapp = item.whatsapp
    listing.external_contact_email = item.email
    listing.last_synced_at = now
    listing.location = point(coordinates[1], coordinates[0]) if coordinates is not None else None


async def upsert(session: AsyncSession, item: NormalizedListing, *, force_primary: bool = False, scope_key: str = "santa_cruz") -> str:
    now = datetime.now(UTC)
    room_capacity = item.room_capacity if item.room_capacity is not None and 1 <= item.room_capacity <= 10 else None
    source = await session.scalar(
        select(SourceRecord).where(
            SourceRecord.source_name == item.source_name, SourceRecord.external_id == item.external_id
        )
    )
    if source is None:
        # Providers can replace a property ID at the same URL, or temporarily
        # omit it and make the adapter fall back to a URL hash. Reuse the URL's
        # durable source/listing identity before entering photo deduplication
        # or INSERT; source_url is independently unique in the database.
        source = await session.scalar(
            select(SourceRecord).where(
                SourceRecord.source_name == item.source_name,
                func.rtrim(func.split_part(func.split_part(SourceRecord.source_url, '#', 1), '?', 1), '/')
                == item.source_url.split('#', 1)[0].split('?', 1)[0].rstrip('/'),
            )
        )
    suppress_new_duplicate = False
    if source:
        listing = await session.get(Listing, source.canonical_listing_id)
    else:
        # The source lookup starts a transaction. Close it before downloading
        # image samples for photo-only cross-source deduplication.
        await session.commit()
        require_no_active_transaction(session, "external image deduplication")
        image_fingerprints = await public_image_fingerprints(item.photos)
        await acquire_duplicate_guard(session)
        listing = await canonical_for(session, item, image_fingerprints)
        if listing is None and image_fingerprints:
            listing = await same_source_canonical_for(session, item, image_fingerprints)
        if listing is None and image_fingerprints:
            duplicate_id = await duplicate_listing_id(
                session,
                image_fingerprints,
                external_only=None,
                rental_mode=item.rental_mode,
            )
            if duplicate_id is not None:
                duplicate = await session.get(Listing, duplicate_id)
                suppress_new_duplicate = bool(duplicate is not None and not duplicate.is_external)

    coordinates = public_location(item)
    source_location_verified = coordinates is not None
    previous_fingerprint = source.fingerprint if source else None

    # Persist the source's latest location state before considering failover.
    # A source without a public point is still a valid catalog source; it just
    # cannot own a map marker. If a verified duplicate exists, prefer it as the
    # primary so the canonical card can keep a trustworthy marker.
    if source:
        source.scope_key = scope_key
        source.raw_payload = item.raw_payload
        source.normalized_payload = normalized_snapshot(item)
        source.fingerprint = item.fingerprint
        source.source_url = item.source_url
        source.source_price_text = item.source_price_text
        source.last_checked_at = source.last_success_at = source.last_seen_at = now
        source.last_discovered_at = now
        source.content_updated_at = now
        source.consecutive_missing_runs = 0
        source.consecutive_unknown_state_runs = 0
        source.current_status = "active"
        source.last_error = None if source_location_verified else "source_location_unverified"
        source.removed_at = None
        source.removed_reason = None

        # A cleanup-suppressed external duplicate must not silently reappear on
        # the next worker cycle. Re-check the *current* remote photos rather
        # than stale title/price/address data. If images cannot be sampled,
        # fail closed and keep the duplicate hidden until a later successful
        # source cycle can prove it is no longer the same gallery.
        if listing is not None and listing.status == "closed" and listing.closed_reason == "duplicate":
            await session.commit()
            require_no_active_transaction(session, "suppressed duplicate recheck")
            current_fingerprints = await public_image_fingerprints(item.photos)
            if not current_fingerprints:
                return "unchanged"
            await acquire_duplicate_guard(session)
            active_duplicate_id = await duplicate_listing_id(
                session,
                current_fingerprints,
                exclude_listing_id=listing.id,
                rental_mode=item.rental_mode,
            )
            same_source_duplicate = None
            if active_duplicate_id is None:
                same_source_duplicate = await same_source_canonical_for(
                    session,
                    item,
                    current_fingerprints,
                )
            if active_duplicate_id is not None or same_source_duplicate is not None:
                await session.commit()
                return "unchanged"

        if (
            not source_location_verified
            and listing is not None
            and listing.primary_source == item.source_name
            and listing.status != "closed"
            and await promote_best_active_source(session, listing.id, require_location=True)
        ):
            await session.commit()
            return "updated"

    # An identical source payload is only a no-op when the primary parser
    # gallery is already reconciled. A transient image failure may leave the
    # listing metadata current but its local media incomplete; that state must
    # retry on the next unchanged source cycle instead of becoming permanent.
    gallery_reconciled = True
    if (
        listing is not None
        and listing.primary_source == item.source_name
        and item.photos
        and get_settings().external_import_download_images
    ):
        stored_image_count = int(
            await session.scalar(
                select(func.count(ListingImage.media_asset_id))
                .join(MediaAsset, MediaAsset.id == ListingImage.media_asset_id)
                .where(
                    ListingImage.listing_id == listing.id,
                    MediaAsset.deleted_at.is_(None),
                )
            )
            or 0
        )
        gallery_reconciled = external_gallery_is_reconciled(
            is_external=listing.is_external,
            external_image_urls=list(listing.external_image_urls or []),
            stored_image_count=stored_image_count,
        )

    # An identical payload is only a no-op while its canonical card is still
    # visible and its primary image gallery is complete. A source may reappear
    # after a confirmed removal; in that case the canonical listing must be
    # restored even though its fingerprint did not change.
    if (
        source
        and previous_fingerprint == item.fingerprint
        and not force_primary
        and source.current_status == "active"
        and listing is not None
        and listing.status != "closed"
        and gallery_reconciled
        and (
            listing.primary_source != item.source_name
            or (coordinates is None and listing.location is None)
            or (coordinates is not None and listing.location is not None)
        )
    ):
        source.last_checked_at = source.last_success_at = source.last_seen_at = now
        source.consecutive_missing_runs = 0
        source.current_status = "active"
        source.last_error = None if source_location_verified else "source_location_unverified"
        await session.commit()
        return "unchanged"
    owner = await system_user(session)
    if not listing:
        listing = Listing(
            owner_user_id=owner.id,
            title=item.title,
            city=item.city,
            area=item.area,
            approximate_address=item.public_address or item.area,
            rental_mode=item.rental_mode,
            monthly_price=item.price_amount if item.rental_mode == "long" else None,
            nightly_price=item.price_amount if item.rental_mode == "holiday" else None,
            weekly_price=item.weekly_price_amount,
            # Existing canonical constraint permits 1..99 or NULL. Studio
            # zero is retained in the source snapshot and Estudio taxonomy.
            bedroom_count=item.bedroom_count if item.bedroom_count else None,
            minimum_stay_months=item.minimum_stay_months,
            minimum_nights=item.minimum_nights,
            deposit_amount=item.deposit_amount,
            deposit_text=item.deposit_text,
            bills_included=item.bills_included,
            bills_text=item.bills_text,
            furnished=item.furnished,
            bathroom=item.bathroom,
            kitchen=item.kitchen,
            room_size_m2=item.room_size_m2,
            room_capacity=min(room_capacity, 2) if room_capacity is not None else None,
            tenant_requirement=item.tenant_requirement,
            room_type=item.room_type,
            location=point(coordinates[1], coordinates[0]) if coordinates is not None else None,
            status="closed" if suppress_new_duplicate else "published",
            closed_reason="duplicate" if suppress_new_duplicate else None,
            is_external=True,
            imported_at=now,
            smoking_allowed=item.smoking_allowed,
            pets_allowed=item.pets_allowed,
            children_allowed=item.children_allowed,
            empadronamiento_allowed=item.empadronamiento_allowed,
            amenities=item.amenities,
            restrictions=item.restrictions,
            advertiser_name=item.advertiser_name,
            advertiser_type=item.advertiser_type,
            available_from=item.available_from,
            published_at=item.published_at or now,
        )
        session.add(listing)
        await session.flush()
        action = "imported"
    else:
        action = "updated"
    restored = action != "imported" and listing.status == "closed"
    replace_primary = (
        not listing.primary_source
        or listing.primary_source == item.source_name
        or force_primary
        or (
            coordinates is not None
            and completeness_score(item) >= listing_completeness_score(listing)
        )
    )
    if replace_primary:
        await apply_primary_source_snapshot(session, listing, item)
        if suppress_new_duplicate:
            listing.status = "closed"
            listing.closed_reason = "duplicate"
        else:
            listing.status = "published"
            listing.closed_reason = None
        listing.location = point(coordinates[1], coordinates[0]) if coordinates is not None else None
    elif restored:
        listing.status = "published"
        listing.closed_reason = None
        listing.last_synced_at = now
    if not source:
        source = SourceRecord(
            source_name=item.source_name,
            scope_key=scope_key,
            external_id=item.external_id,
            source_url=item.source_url,
            canonical_listing_id=listing.id,
            raw_payload=item.raw_payload,
            normalized_payload=normalized_snapshot(item),
            fingerprint=item.fingerprint,
        )
        session.add(source)
    source.raw_payload = item.raw_payload
    source.normalized_payload = normalized_snapshot(item)
    source.fingerprint = item.fingerprint
    source.source_url = item.source_url
    source.source_price_text = item.source_price_text
    source.last_checked_at = source.last_success_at = source.last_seen_at = source.content_updated_at = now
    source.last_discovered_at = now
    source.consecutive_missing_runs = 0
    source.consecutive_unknown_state_runs = 0
    source.current_status = "active"
    source.last_error = None if source_location_verified else "source_location_unverified"
    source.removed_at = None
    source.removed_reason = None
    if action != "unchanged" or restored:
        await touch_catalog(session)

    if (action == "imported" or restored) and listing.status == "published":
        await notify_saved_search_matches(session, listing)

    result = "restored" if restored else action
    listing_id = listing.id
    owner_id = owner.id
    should_import_images = replace_primary and not force_primary and bool(item.photos) and item.photos_complete
    # Make the listing/source state durable before any remote image or object
    # storage I/O. Image failures are deliberately non-fatal fallbacks.
    await session.commit()
    if should_import_images:
        await import_images(session, listing_id, owner_id, item.photos)
    return result


async def promote_best_active_source(
    session: AsyncSession,
    canonical_listing_id,
    *,
    require_location: bool = False,
    lifecycle_only: bool = False,
) -> bool:
    rows = (
        await session.scalars(
            select(SourceRecord).where(
                SourceRecord.canonical_listing_id == canonical_listing_id,
                SourceRecord.current_status == "active",
            )
        )
    ).all()
    candidates: list[NormalizedListing] = []
    for row in rows:
        if not row.normalized_payload:
            continue
        candidate = listing_from_snapshot(row.normalized_payload)
        if require_location and public_location(candidate) is None:
            continue
        candidates.append(candidate)
    if not candidates:
        return False
    best = max(
        candidates,
        key=lambda candidate: (public_location(candidate) is not None, completeness_score(candidate)),
    )
    if lifecycle_only:
        listing = await session.get(Listing, canonical_listing_id)
        if listing is None or not listing.is_external:
            raise ValueError("Primary promotion requires an external canonical listing")
        await apply_primary_source_snapshot(session, listing, best)
        if listing.closed_reason != "duplicate":
            listing.status, listing.closed_reason = "published", None
        await touch_catalog(session)
        return True
    outcome = await upsert(session, best, force_primary=True)
    return outcome in {"imported", "updated", "unchanged", "restored"}


async def deactivate_source_record(session: AsyncSession, row: SourceRecord, reason: str) -> int:
    """Deactivate one source and atomically promote an active duplicate or close the listing."""
    if row.current_status != "active":
        return 0
    row.current_status = "missing" if reason in {"deleted", "removed", "expired", "not_found", "source_removed"} else reason
    row.removed_at = datetime.now(UTC)
    row.removed_reason = reason
    row.last_error = reason
    listing = await session.get(Listing, row.canonical_listing_id)
    if not listing or listing.primary_source != row.source_name:
        return 0
    if await promote_best_active_source(session, listing.id):
        return 0
    listing.status = "closed"
    listing.closed_reason = reason
    listing.last_synced_at = datetime.now(UTC)
    await notify_favorited_listing_unavailable(session, listing, event_key=f"external:{row.id}:{reason}")
    await touch_catalog(session)
    return 1


async def retire_source_records(session: AsyncSession, source_names: set[str]) -> int:
    """Retire active records from providers deliberately removed from crawling.

    Retiring a provider is different from a temporary source failure: its
    stored records remain for attribution, while an active duplicate is
    promoted when present and otherwise the public canonical listing closes.
    This avoids indefinitely advertising a record that can no longer be
    reconciled through a compliant route.
    """
    if not source_names:
        return 0
    rows = (
        await session.scalars(
            select(SourceRecord).where(
                func.lower(SourceRecord.source_name).in_({name.casefold() for name in source_names}),
                SourceRecord.current_status == "active",
            )
        )
    ).all()
    retired = 0
    for row in rows:
        retired += await deactivate_source_record(session, row, "source_retired")
    await session.commit()
    return retired


async def archive_missing(
    session: AsyncSession, source: ExternalListingSource | str, started_at: datetime,
    *, report: dict[str, int] | None = None,
) -> int:
    # Keep the public adapter protocol duck-typed: test adapters and future
    # sources need only expose ``name`` and ``check_listing_state``.
    source_name = source if isinstance(source, str) else source.name
    scope_key = "santa_cruz" if isinstance(source, str) else getattr(source, "scope_key", "santa_cruz")
    from .external_removal import log_removal_anomaly, removal_anomaly_reason
    candidate_count = int(await session.scalar(
        select(func.count()).select_from(SourceRecord).where(
            SourceRecord.source_name == source_name,
            SourceRecord.scope_key == scope_key,
            SourceRecord.current_status == "active",
            SourceRecord.last_seen_at < started_at,
        )
    ) or 0)
    await session.commit()
    async def candidate_ids():
        last_id = None
        while True:
            query = select(SourceRecord.id, SourceRecord.source_url).where(
                SourceRecord.source_name == source_name,
                SourceRecord.scope_key == scope_key,
                SourceRecord.current_status == "active",
                SourceRecord.last_seen_at < started_at,
            ).order_by(SourceRecord.id).limit(100)
            if last_id is not None:
                query = query.where(SourceRecord.id > last_id)
            batch = (await session.execute(query)).all()
            # Never hold a database transaction while probing remote details.
            await session.commit()
            if not batch:
                break
            last_id = batch[-1][0]
            states = []
            for _row_id, source_url in batch:
                require_no_active_transaction(session, "external listing state check")
                states.append("unknown" if isinstance(source, str) else await source.check_listing_state(source_url))
            reason = removal_anomaly_reason(states, candidate_count)
            if reason:
                log_removal_anomaly(source_name, reason)
                if report is not None:
                    report["removal_anomaly_batches"] += 1
                    report["removal_anomaly_records"] += sum(state in {"removed", "expired", "not_found"} for state in states)
                return
            for (row_id, _source_url), state in zip(batch, states):
                yield row_id, state

    archived = 0
    async for row_id, state in candidate_ids():
        row = await session.get(SourceRecord, row_id)
        if not row or row.current_status != "active":
            await session.commit()
            continue
        row.last_state_check_at = datetime.now(UTC)
        row.last_state_check_result = state
        if state in {"removed", "expired", "not_found"}:
            from .external_removal import purge_confirmed_removed_source
            outcome = await purge_confirmed_removed_source(session, row.id, state)
            archived += outcome["canonical_listings_purged"]
        elif state == "active":
            row.last_seen_at = datetime.now(UTC)
            row.consecutive_missing_runs = 0
            row.consecutive_unknown_state_runs = 0
        elif state in {"blocked", "temporary_error"}:
            row.last_error = state
        else:
            # Unknown is not a missing result. Keep a separate conservative
            # fallback counter so blocked/temporary outcomes never poison
            # normal reconciliation diagnostics.
            row.consecutive_unknown_state_runs += 1

        await session.commit()
    return archived


async def run_removal_check(session: AsyncSession, source: ExternalListingSource, **kwargs) -> int:
    """Sweep active operational rows; historical soft-missing rows remain untouched."""
    from .external_removal import reconcile_source
    return await reconcile_source(session, source, **kwargs)


async def archive_confirmed_not_found(session: AsyncSession, source_name: str, source_url: str) -> int:
    """Compatibility wrapper for detail fetches that already proved a 404."""
    row = await session.scalar(
        select(SourceRecord).where(SourceRecord.source_name == source_name, SourceRecord.source_url == source_url)
    )
    if not row:
        return 0
    row.last_state_check_at = datetime.now(UTC)
    row.last_state_check_result = "not_found"
    from .external_removal import purge_confirmed_removed_source
    outcome = await purge_confirmed_removed_source(session, row.id, "not_found")
    return outcome["canonical_listings_purged"]


async def deactivate_rejected_source(session: AsyncSession, source_name: str, source_url: str) -> None:
    """Do not keep an already imported record visible after strict room validation rejects it."""
    row = await session.scalar(
        select(SourceRecord).where(SourceRecord.source_name == source_name, SourceRecord.source_url == source_url)
    )
    if not row:
        return
    await deactivate_source_record(session, row, "rejected")


async def reconcile_unverified_source_locations(session: AsyncSession, source_name: str, scope_key: str = "santa_cruz") -> int:
    """Remove legacy invented markers while keeping valid cards in the catalog."""
    missing_coordinates = or_(
        SourceRecord.normalized_payload["latitude"].astext.is_(None),
        SourceRecord.normalized_payload["longitude"].astext.is_(None),
    )
    rows = (
        await session.scalars(
            select(SourceRecord).join(Listing, Listing.id == SourceRecord.canonical_listing_id).where(
                SourceRecord.source_name == source_name,
                SourceRecord.scope_key == scope_key,
                SourceRecord.current_status == "active",
                Listing.primary_source == source_name,
                or_(
                    and_(missing_coordinates, Listing.location.is_not(None)),
                    Listing.closed_reason == "source_location_unverified",
                    and_(~missing_coordinates, SourceRecord.last_error == "source_location_unverified"),
                ),
            ).order_by(SourceRecord.id).limit(100)
        )
    ).all()
    changed = 0
    for row in rows:
        payload = row.normalized_payload or {}
        if "latitude" not in payload or "longitude" not in payload:
            continue
        if payload.get("latitude") is not None and payload.get("longitude") is not None:
            if row.last_error == "source_location_unverified":
                row.last_error = None
            continue

        row.last_error = "source_location_unverified"
        listing = await session.get(Listing, row.canonical_listing_id)
        if listing is None or listing.primary_source != row.source_name:
            continue
        if listing.status == "closed" and listing.closed_reason != "source_location_unverified":
            continue

        if await promote_best_active_source(session, listing.id, require_location=True):
            changed += 1
            continue

        needs_catalog_touch = (
            listing.location is not None
            or listing.status == "closed"
            or listing.closed_reason == "source_location_unverified"
        )
        listing.location = None
        listing.last_synced_at = datetime.now(UTC)
        if listing.closed_reason == "source_location_unverified":
            listing.status = "published"
            listing.closed_reason = None
        if needs_catalog_touch:
            await touch_catalog(session)
            changed += 1

    await session.commit()
    return changed


async def run_source(session: AsyncSession, source: ExternalListingSource, run_id: str, *, max_details: int | None = None) -> SourceRunCounters:
    started = perf_counter()
    scope_key = getattr(source, "scope_key", "santa_cruz")
    counters = SourceRunCounters({
        key: 0
        for key in (
            "discovered",
            "discovered_urls",
            "new_discovered",
            "fetched",
            "fetched_details",
            "imported",
            "created",
            "updated",
            "unchanged",
            "restored",
            "filtered_not_room",
            "rejected_not_room",
            "rejected_unsupported_property_type",
            "filtered_wrong_location",
            "rejected_wrong_location",
            "accepted_rooms",
            "accepted_rentals",
            "accepted_long",
            "accepted_holiday",
            "accepted_studios",
            "accepted_one_bedroom",
            "archived",
            "failed",
            "failed_details",
            "incomplete_galleries",
            "removal_anomaly_batches",
            "removal_anomaly_records",
            "rejected_invalid_price",
        )
    })
    run = ExternalImportRun(run_id=run_id, source_name=source.name, scope_key=scope_key)
    session.add(run)
    await session.commit()
    reconciled_locations = await reconcile_unverified_source_locations(session, source.name, scope_key)
    if reconciled_locations:
        logger.info(
            "external_import_reconciled_unverified_locations",
            extra={"source": source.name, "updated_or_promoted": reconciled_locations},
        )
    started_at = datetime.now(UTC)
    previous_block = await session.scalar(
        select(ExternalImportRun)
        .where(
            ExternalImportRun.source_name == source.name,
            ExternalImportRun.scope_key == scope_key,
            ExternalImportRun.result == "blocked",
            ExternalImportRun.next_check_at > started_at,
        )
        .order_by(ExternalImportRun.next_check_at.desc())
        .limit(1)
    )
    if previous_block:
        run.result = "blocked"
        run.last_error = previous_block.last_error
        run.challenge_type = previous_block.challenge_type
        run.http_status = previous_block.http_status
        run.final_url = previous_block.final_url
        run.next_check_at = previous_block.next_check_at
        run.diagnostic_paths = previous_block.diagnostic_paths
        run.counters = counters
        run.finished_at = datetime.now(UTC)
        await session.commit()
        await source.close()
        EXTERNAL_IMPORTS.labels(source.name, run.result).inc()
        EXTERNAL_IMPORT_DURATION.labels(source.name).observe(perf_counter() - started)
        counters.result = run.result
        return counters
    # The backoff lookup starts an implicit transaction. Discovery may involve
    # many pages and browser fallbacks, so close the transaction first.
    await session.commit()
    try:
        require_no_active_transaction(session, "external source discovery")
        discovery = await source.discover_listing_urls()
        if isinstance(discovery, list):
            discovery = DiscoveryResult(urls=set(discovery), complete=True, visited_pages=1, reached_last_page=True)
        urls = discovery.urls
        if max_details is not None and len(urls) > max_details:
            # Bootstrap sampling must never reconcile unseen offers as absent.
            discovery.complete = False
            discovery.failed_pages.append("bootstrap_detail_budget")
        previous_success = await session.scalar(
            select(ExternalImportRun)
            .where(
                ExternalImportRun.source_name == source.name,
                ExternalImportRun.scope_key == scope_key,
                ExternalImportRun.result == "success",
                ExternalImportRun.id != run.id,
            )
            .order_by(ExternalImportRun.finished_at.desc())
            .limit(1)
        )
        previous_discovered = int((previous_success.counters or {}).get("discovered_urls", 0)) if previous_success else 0
        suspicious_drop = bool(previous_discovered) and len(urls) < max(1, previous_discovered * 0.3)
        if (not urls and previous_discovered) or suspicious_drop:
            discovery.complete = False
            discovery.failed_pages.append("suspicious_discovery_volume_drop")
        counters["discovered"] = len(urls)
        counters["discovered_urls"] = len(urls)
        run.discovery_complete = discovery.complete
        run.discovery_pages = discovery.visited_pages
        run.discovery_failed_pages = discovery.failed_pages
        if discovery.blocked:
            run.result = "blocked"
            run.last_error = "discovery blocked"
            run.counters = counters
            run.finished_at = datetime.now(UTC)
            await session.commit()
            await source.close()
            EXTERNAL_IMPORTS.labels(source.name, run.result).inc()
            EXTERNAL_IMPORT_DURATION.labels(source.name).observe(perf_counter() - started)
            counters.result = run.result
            return counters
        source.not_found_urls.clear()
        getattr(source, "removed_urls", set()).clear()
        if urls:
            known_urls = set()
            ordered_urls = sorted(urls)
            for start in range(0, len(ordered_urls), 250):
                rows = await session.scalars(
                    select(SourceRecord).where(
                        SourceRecord.source_name == source.name,
                        SourceRecord.scope_key == scope_key,
                        SourceRecord.source_url.in_(ordered_urls[start:start + 250]),
                    )
                )
                for row in rows:
                    known_urls.add(row.source_url)
                    row.last_seen_at = started_at
                    row.last_discovered_at = started_at
                    row.consecutive_missing_runs = 0
                    row.consecutive_unknown_state_runs = 0
            counters["new_discovered"] = len(urls - known_urls)
        # Persist discovery metadata, then release the DB connection before the
        # concurrent detail fetches. Each accepted/rejected detail is committed
        # independently below.
        await session.commit()
        semaphore = asyncio.Semaphore(get_settings().external_import_max_concurrency_per_source)

        async def fetch(url: str):
            async with semaphore:
                return url, await source.fetch_listing(url)

        require_no_active_transaction(session, "external detail fetch")
        async def fetch_batches():
            ordered_urls = sorted(urls)
            if max_details is not None:
                ordered_urls = ordered_urls[:max_details]
            for start in range(0, len(ordered_urls), 100):
                results = await asyncio.gather(
                    *(fetch(url) for url in ordered_urls[start:start + 100]), return_exceptions=True
                )
                from .external_removal import log_removal_anomaly, removal_anomaly_reason
                states = [
                    "temporary_error" if isinstance(result, BaseException) else
                    "not_found" if result[0] in source.not_found_urls else
                    "removed" if result[0] in getattr(source, "removed_urls", set()) else
                    "active" if result[1] else "unknown"
                    for result in results
                ]
                reason = removal_anomaly_reason(states, len(ordered_urls))
                if reason:
                    counters["removal_anomaly_batches"] += 1
                    counters["removal_anomaly_records"] += sum(state in {"removed", "expired", "not_found"} for state in states)
                    log_removal_anomaly(source.name, reason)
                    return
                for result in results:
                    yield result

        partial = False
        async for result in fetch_batches():
            if isinstance(result, SourceBlocked):
                raise result
            if isinstance(result, BaseException):
                counters["failed_details"] += 1
                partial = True
                logger.warning("external_detail_failed", exc_info=result, extra={"source": source.name})
                continue
            url, document = result
            if not document:
                if url in source.not_found_urls:
                    counters["archived"] += await archive_confirmed_not_found(session, source.name, url)
                elif url in getattr(source, "removed_urls", set()):
                    removed_record = await session.scalar(
                        select(SourceRecord).where(
                            SourceRecord.source_name == source.name,
                            SourceRecord.source_url == url,
                        )
                    )
                    if removed_record:
                        removed_record.last_state_check_at = datetime.now(UTC)
                        removed_record.last_state_check_result = "removed"
                        from .external_removal import purge_confirmed_removed_source
                        purge_outcome = await purge_confirmed_removed_source(session, removed_record.id, "removed")
                        counters["archived"] += purge_outcome["canonical_listings_purged"]
                await session.commit()
                continue
            counters["fetched"] += 1
            counters["fetched_details"] += 1
            parsed = source.parse_listing(document, url)
            if property_type(parsed, source.name) is None:
                counters["rejected_unsupported_property_type"] += 1
                # Retain historical observability consumers during transition.
                counters["filtered_not_room"] += 1
                counters["rejected_not_room"] += 1
                await deactivate_rejected_source(session, source.name, url)
                await session.commit()
                continue
            if not (source.accepts_location(parsed) if hasattr(source, "accepts_location") else is_in_import_scope(parsed, scope_key)):
                counters["filtered_wrong_location"] += 1
                counters["rejected_wrong_location"] += 1
                await deactivate_rejected_source(session, source.name, url)
                await session.commit()
                continue
            item = source.normalize_listing(parsed, url)
            if not item:
                counters["rejected_invalid_price"] += 1
                await deactivate_rejected_source(session, source.name, url)
                await session.commit()
                continue
            counters["accepted_rentals"] += 1
            if not item.photos_complete:
                counters["incomplete_galleries"] += 1
                partial = True
            counters[f"accepted_{item.rental_mode}"] += 1
            counters["accepted_rooms" if item.room_type in ROOM_TYPES else "accepted_studios" if item.room_type == "Estudio" else "accepted_one_bedroom"] += 1
            outcome = await upsert(session, item, scope_key=scope_key)
            counters[outcome] += 1
            if outcome == "imported":
                counters["created"] += 1
        await session.commit()
        partial = partial or bool(counters["removal_anomaly_batches"])
        if discovery.complete and not partial:
            counters["archived"] += await archive_missing(session, source, started_at, report=counters)
            partial = partial or bool(counters["removal_anomaly_batches"])
        completed_contract = completed_source_contract(counters)
        if discovery.complete and not partial and completed_contract:
            run.result = "success"
        else:
            run.result = "partial"
            if not completed_contract:
                run.last_error = "No valid rental detail completed the external import contract"
    except SourceBlocked as exc:
        run.result = "blocked"
        run.last_error = str(exc)
        diagnostic = source.blocked_diagnostic or {}
        run.challenge_type = str(diagnostic.get("challenge_type") or "access_challenge")
        run.http_status = diagnostic.get("status")
        run.final_url = diagnostic.get("final_url")
        run.diagnostic_paths = diagnostic.get("paths") or {}
        previous_challenges = await session.scalar(
            select(ExternalImportRun).where(
                ExternalImportRun.source_name == source.name,
                ExternalImportRun.scope_key == scope_key,
                ExternalImportRun.result == "blocked",
            )
        )
        delay_hours = 12 if previous_challenges else 6
        run.next_check_at = datetime.now(UTC) + timedelta(hours=delay_hours)
        counters["failed"] += 1
    except Exception as exc:
        await session.rollback()
        run.result = "failed"
        run.last_error = str(exc)
        session.add(run)
        counters["failed"] += 1
        logger.exception("external_source_failed", extra={"run_id": run_id, "source": source.name})
    run.counters = counters
    run.finished_at = datetime.now(UTC)
    await session.commit()
    await source.close()
    EXTERNAL_IMPORTS.labels(source.name, run.result).inc()
    EXTERNAL_IMPORT_DURATION.labels(source.name).observe(perf_counter() - started)
    counters.result = run.result
    return counters
