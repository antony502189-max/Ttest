from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
from time import perf_counter
from uuid import UUID, uuid4

import httpx
from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]
from fastapi import HTTPException
from PIL import Image
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.v1.uploads import validate_and_normalize
from ..core.config import get_settings
from ..core.observability import EXTERNAL_IMPORT_DURATION, EXTERNAL_IMPORTS
from ..external_sources import (
    DiscoveryResult,
    ExternalListingSource,
    NormalizedListing,
    SourceBlocked,
    is_in_target_province,
    is_rental,
    is_room_offer,
    parse_optional_date,
    parse_optional_datetime,
)
from ..models import CatalogState, ExternalImportRun, Listing, ListingImage, MediaAsset, User
from ..models import ExternalListingSource as SourceRecord
from ..repositories.listings import point
from ..storage import get_storage

logger = logging.getLogger(__name__)
SYSTEM_EMAIL = "external-import@112233.es"


def require_no_active_transaction(session: AsyncSession, operation: str) -> None:
    """Fail closed if a future refactor puts remote I/O inside a DB transaction."""
    if session.in_transaction():
        raise RuntimeError(f"Database transaction must be closed before {operation}")


class SourceRunCounters(dict[str, int]):
    """Counters plus the terminal state for the worker's aggregate health."""

    result: str = "failed"

MUNICIPALITY_POINTS = {
    "santa cruz de tenerife": (28.4636, -16.2518),
    "la laguna": (28.4874, -16.3159),
    "san cristobal de la laguna": (28.4874, -16.3159),
    "san cristóbal de la laguna": (28.4874, -16.3159),
    "arona": (28.0996, -16.6809),
    "adeje": (28.1227, -16.7244),
    "granadilla": (28.1188, -16.5760),
    "granadilla de abona": (28.1188, -16.5760),
    "puerto de la cruz": (28.4134, -16.5509),
    "agulo": (28.1874, -17.1961),
    "alajero": (28.0622, -17.2383),
    "alajeró": (28.0622, -17.2383),
    "arafo": (28.3404, -16.4151),
    "arico": (28.1667, -16.4833),
    "barlovento": (28.8283, -17.8038),
    "brena alta": (28.6627, -17.7873),
    "breña alta": (28.6627, -17.7873),
    "brena baja": (28.6305, -17.7761),
    "breña baja": (28.6305, -17.7761),
    "buenavista del norte": (28.3727, -16.8502),
    "candelaria": (28.3536, -16.3713),
    "el paso": (28.6513, -17.8826),
    "el pinar de el hierro": (27.7249, -17.9811),
    "el rosario": (28.4477, -16.3787),
    "el sauzal": (28.4767, -16.4364),
    "el tanque": (28.3669, -16.8314),
    "fasnia": (28.2368, -16.4388),
    "fuencaliente": (28.4940, -17.8452),
    "garachico": (28.3723, -16.7634),
    "garafia": (28.8159, -17.9432),
    "garafía": (28.8159, -17.9432),
    "la frontera": (27.7541, -18.0030),
    "la guancha": (28.3743, -16.6512),
    "la matanza de acentejo": (28.4529, -16.4455),
    "la orotava": (28.3907, -16.5230),
    "la victoria de acentejo": (28.4326, -16.4630),
    "la palma": (28.6835, -17.7642),
    "la gomera": (28.1009, -17.1105),
    "el hierro": (27.7464, -18.0116),
    "los llanos de aridane": (28.6587, -17.9182),
    "los realejos": (28.3847, -16.5825),
    "los silos": (28.3642, -16.8156),
    "puntagorda": (28.7743, -17.9774),
    "puntallana": (28.7398, -17.7427),
    "san andres y sauces": (28.8004, -17.7581),
    "san andrés y sauces": (28.8004, -17.7581),
    "san juan de la rambla": (28.3919, -16.6514),
    "san miguel de abona": (28.0984, -16.6171),
    "san sebastian de la gomera": (28.0900, -17.1101),
    "san sebastián de la gomera": (28.0900, -17.1101),
    "santa cruz de la palma": (28.6835, -17.7642),
    "santa ursula": (28.4265, -16.4890),
    "santa úrsula": (28.4265, -16.4890),
    "santiago del teide": (28.2957, -16.8164),
    "tacoronte": (28.4769, -16.4108),
    "tazacorte": (28.6419, -17.9333),
    "tegueste": (28.5184, -16.3162),
    "tijarafe": (28.7110, -17.9552),
    "valle gran rey": (28.1042, -17.3255),
    "vallehermoso": (28.1805, -17.2642),
    "valverde": (27.8064, -17.9162),
    "vilaflor de chasna": (28.1573, -16.6380),
}


def public_location(item: NormalizedListing) -> tuple[float, float] | None:
    if item.latitude is not None and item.longitude is not None:
        return item.latitude, item.longitude
    city = item.city.casefold()
    return next((coordinates for name, coordinates in MUNICIPALITY_POINTS.items() if name in city), None)


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


def perceptual_hash(content: bytes) -> str:
    """A stable average hash for conservative duplicate-photo matching."""
    with Image.open(BytesIO(content)) as image:
        pixels = [int(value) for value in image.convert("L").resize((8, 8)).get_flattened_data()]
    average = sum(pixels) / len(pixels)
    return f"{sum((1 << index) for index, value in enumerate(pixels) if value >= average):016x}"


async def public_image_hashes(urls: list[str]) -> set[str]:
    if not urls:
        return set()
    result: set[str] = set()
    async with httpx.AsyncClient(
        timeout=get_settings().external_import_request_timeout_seconds, follow_redirects=True
    ) as client:
        for url in urls[:5]:
            try:
                response = await client.get(url, headers={"User-Agent": get_settings().external_import_user_agent})
                content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                if response.status_code != 200 or not content_type.startswith("image/"):
                    continue
                normalized, _, _ = await asyncio.to_thread(validate_and_normalize, response.content)
                result.add(await asyncio.to_thread(perceptual_hash, normalized))
            except (HTTPException, OSError, ValueError, httpx.HTTPError):
                continue
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


async def download_external_image(client: httpx.AsyncClient, url: str) -> PreparedExternalImage | None:
    response = await client.get(url, headers={"User-Agent": get_settings().external_import_user_agent})
    content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
    if (
        response.status_code != 200
        or not content_type.startswith("image/")
        or len(response.content) > get_settings().max_upload_bytes
    ):
        return None
    normalized, width, height = await asyncio.to_thread(validate_and_normalize, response.content)
    return PreparedExternalImage(
        content=normalized,
        width=width,
        height=height,
        checksum=hashlib.sha256(normalized).hexdigest(),
        perceptual_hash=await asyncio.to_thread(perceptual_hash, normalized),
    )


async def import_images(
    session: AsyncSession,
    listing_id: UUID,
    owner_id: UUID,
    urls: list[str],
) -> None:
    """Persist public images without holding a database transaction during HTTP, CPU, or storage I/O."""
    if not get_settings().external_import_download_images or not urls:
        return
    existing_images = (
        await session.execute(
            select(ListingImage.media_asset_id, ListingImage.sort_order).where(ListingImage.listing_id == listing_id)
        )
    ).all()
    attached = {media_asset_id for media_asset_id, _ in existing_images}
    next_sort_order = max((sort_order for _, sort_order in existing_images), default=-1) + 1
    # The lookup above starts an implicit transaction. Close it before the
    # first remote request so slow or malicious hosts cannot pin a DB snapshot.
    await session.commit()

    storage = get_storage()
    async with httpx.AsyncClient(
        timeout=get_settings().external_import_request_timeout_seconds, follow_redirects=True
    ) as client:
        for image_position, url in enumerate(urls[:20]):
            require_no_active_transaction(session, "external image download")
            try:
                prepared = await download_external_image(client, url)
            except (HTTPException, OSError, ValueError, httpx.HTTPError):
                logger.info(
                    "external_image_skipped",
                    extra={"listing_id": str(listing_id), "image_position": image_position},
                )
                continue
            if prepared is None:
                continue

            created_storage_key: str | None = None
            try:
                # Reuse only assets owned by the importer. Reusing another
                # user's private listing image would make that asset public.
                asset = await session.scalar(
                    select(MediaAsset).where(
                        MediaAsset.owner_id == owner_id,
                        MediaAsset.checksum == prepared.checksum,
                        MediaAsset.kind == "listing_image",
                        MediaAsset.deleted_at.is_(None),
                    )
                )
                if not asset:
                    # Close the checksum lookup transaction before S3/MinIO I/O.
                    await session.commit()
                    asset_id = uuid4()
                    created_storage_key = external_storage_key(owner_id, asset_id)
                    require_no_active_transaction(session, "external image storage")
                    try:
                        await asyncio.to_thread(storage.put, created_storage_key, prepared.content)
                    except (OSError, BotoCoreError, ClientError):
                        logger.exception(
                            "external_image_storage_failed",
                            extra={"listing_id": str(listing_id), "image_position": image_position},
                        )
                        continue
                    asset = MediaAsset(
                        id=asset_id,
                        owner_id=owner_id,
                        storage_key=created_storage_key,
                        mime_type="image/webp",
                        size_bytes=len(prepared.content),
                        width=prepared.width,
                        height=prepared.height,
                        checksum=prepared.checksum,
                        perceptual_hash=prepared.perceptual_hash,
                        kind="listing_image",
                    )
                    session.add(asset)
                    await session.flush()
                if asset.id not in attached:
                    session.add(
                        ListingImage(
                            listing_id=listing_id,
                            media_asset_id=asset.id,
                            sort_order=next_sort_order,
                            is_cover=next_sort_order == 0,
                        )
                    )
                    attached.add(asset.id)
                    next_sort_order += 1
                await session.commit()
            except SQLAlchemyError:
                await session.rollback()
                if created_storage_key is not None:
                    try:
                        await asyncio.to_thread(storage.delete, created_storage_key)
                    except (OSError, BotoCoreError, ClientError):
                        logger.exception(
                            "external_image_cleanup_failed",
                            extra={"listing_id": str(listing_id), "image_position": image_position},
                        )
                logger.exception(
                    "external_image_persistence_failed",
                    extra={"listing_id": str(listing_id), "image_position": image_position},
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
        allow_contact_form=False,
    )
    session.add(user)
    await session.flush()
    return user


async def canonical_for(session: AsyncSession, item: NormalizedListing, image_hashes: set[str]) -> Listing | None:
    terms = [value for value in (item.phone, item.whatsapp, item.email) if value]
    if terms:
        contact_match = await session.scalar(
            select(Listing).where(
                Listing.is_external.is_(True),
                or_(
                    Listing.external_contact_phone.in_(terms),
                    Listing.external_contact_whatsapp.in_(terms),
                    Listing.external_contact_email.in_(terms),
                ),
            )
        )
        if contact_match:
            return contact_match
    if image_hashes:
        image_matches = (
            await session.scalars(
                select(Listing)
                .join(ListingImage, ListingImage.listing_id == Listing.id)
                .join(MediaAsset, MediaAsset.id == ListingImage.media_asset_id)
                .where(
                    Listing.is_external.is_(True),
                    Listing.deleted_at.is_(None),
                    MediaAsset.perceptual_hash.in_(image_hashes),
                )
                .distinct()
            )
        ).all()
        for candidate in image_matches:
            if (
                similarity(candidate.title, item.title) >= 0.78
                and similarity(candidate.description, item.description) >= 0.78
            ):
                return candidate
    price_column = Listing.monthly_price if item.rental_mode == "long" else Listing.nightly_price
    candidates = (
        await session.scalars(
            select(Listing).where(
                Listing.is_external.is_(True),
                Listing.city.ilike(f"%{item.city}%"),
                price_column == item.price_amount,
            )
        )
    ).all()
    for candidate in candidates:
        title_score = similarity(candidate.title, item.title)
        description_score = similarity(candidate.description, item.description)
        if title_score >= 0.9 or (title_score >= 0.78 and description_score >= 0.9):
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


async def touch_catalog(session: AsyncSession) -> None:
    state = await session.get(CatalogState, 1)
    if not state:
        state = CatalogState(id=1, version=1)
        session.add(state)
    state.version += 1
    state.updated_at = datetime.now(UTC)


async def upsert(session: AsyncSession, item: NormalizedListing, *, force_primary: bool = False) -> str:
    now = datetime.now(UTC)
    source = await session.scalar(
        select(SourceRecord).where(
            SourceRecord.source_name == item.source_name, SourceRecord.external_id == item.external_id
        )
    )
    if source:
        listing = await session.get(Listing, source.canonical_listing_id)
    else:
        # The source lookup starts a transaction. Close it before downloading
        # image samples for conservative cross-source deduplication.
        await session.commit()
        require_no_active_transaction(session, "external image deduplication")
        image_hashes = await public_image_hashes(item.photos)
        listing = await canonical_for(session, item, image_hashes)
    # An identical payload is only a no-op while its canonical card is still
    # visible. A source may reappear after a confirmed removal; in that case
    # the canonical listing must be restored even though its fingerprint did
    # not change.
    if (
        source
        and source.fingerprint == item.fingerprint
        and not force_primary
        and source.current_status == "active"
        and listing is not None
        and listing.status != "closed"
    ):
        source.last_checked_at = source.last_success_at = source.last_seen_at = now
        source.consecutive_missing_runs = 0
        source.current_status = "active"
        await session.commit()
        return "unchanged"
    owner = await system_user(session)
    coordinates = public_location(item)
    if not listing and coordinates is None:
        # The canonical listing requires a map point; never invent one.
        await session.commit()
        return "filtered_wrong_location"
    if not listing:
        if coordinates is None:
            raise RuntimeError("unreachable: missing external listing coordinates")
        listing = Listing(
            owner_user_id=owner.id,
            title=item.title,
            city=item.city,
            area=item.area,
            approximate_address=item.area,
            rental_mode=item.rental_mode,
            monthly_price=item.price_amount if item.rental_mode == "long" else None,
            nightly_price=item.price_amount if item.rental_mode == "holiday" else None,
            weekly_price=item.price_amount if item.price_period == "week" else None,
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
            room_capacity=item.room_capacity,
            tenant_requirement=item.tenant_requirement,
            room_type=item.room_type,
            location=point(coordinates[1], coordinates[0]),
            status="published",
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
    restored = listing.status == "closed"
    replace_primary = (
        not listing.primary_source
        or listing.primary_source == item.source_name
        or force_primary
        or completeness_score(item) >= listing_completeness_score(listing)
    )
    if replace_primary:
        listing.title = item.title
        listing.description = item.description
        listing.home_description = item.description
        listing.city = item.city
        listing.area = item.area
        listing.approximate_address = item.area
        listing.rental_mode = item.rental_mode
        listing.room_type = item.room_type
        listing.monthly_price = item.price_amount if item.rental_mode == "long" else None
        listing.nightly_price = item.price_amount if item.rental_mode == "holiday" else None
        listing.weekly_price = item.price_amount if item.price_period == "week" else None
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
        listing.room_capacity = item.room_capacity
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
        listing.status = "published"
        if coordinates is not None:
            listing.location = point(coordinates[1], coordinates[0])
    elif restored:
        listing.status = "published"
        listing.last_synced_at = now
    if not source:
        source = SourceRecord(
            source_name=item.source_name,
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
    source.last_error = None
    source.removed_at = None
    source.removed_reason = None
    if action != "unchanged" or restored:
        await touch_catalog(session)

    result = "restored" if restored else action
    listing_id = listing.id
    owner_id = owner.id
    should_import_images = replace_primary and not force_primary and bool(item.photos)
    # Make the listing/source state durable before any remote image or object
    # storage I/O. Image failures are deliberately non-fatal fallbacks.
    await session.commit()
    if should_import_images:
        await import_images(session, listing_id, owner_id, item.photos)
    return result


async def promote_best_active_source(session: AsyncSession, canonical_listing_id) -> bool:
    rows = (
        await session.scalars(
            select(SourceRecord).where(
                SourceRecord.canonical_listing_id == canonical_listing_id,
                SourceRecord.current_status == "active",
            )
        )
    ).all()
    snapshots = [row for row in rows if row.normalized_payload]
    if not snapshots:
        return False
    best = max(snapshots, key=lambda row: completeness_score(listing_from_snapshot(row.normalized_payload)))
    await upsert(session, listing_from_snapshot(best.normalized_payload), force_primary=True)
    return True


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
    await touch_catalog(session)
    return 1


async def archive_missing(session: AsyncSession, source: ExternalListingSource | str, started_at: datetime) -> int:
    # Keep the public adapter protocol duck-typed: test adapters and future
    # sources need only expose ``name`` and ``check_listing_state``.
    source_name = source if isinstance(source, str) else source.name
    candidates = (
        await session.execute(
            select(SourceRecord.id, SourceRecord.source_url).where(
                SourceRecord.source_name == source_name,
                SourceRecord.current_status == "active",
                SourceRecord.last_seen_at < started_at,
            )
        )
    ).all()
    # Do not hold the candidate-query transaction while remote state probes run.
    await session.commit()

    archived = 0
    for row_id, source_url in candidates:
        require_no_active_transaction(session, "external listing state check")
        state = "unknown" if isinstance(source, str) else await source.check_listing_state(source_url)
        row = await session.get(SourceRecord, row_id)
        if not row or row.current_status != "active":
            await session.commit()
            continue
        row.last_state_check_at = datetime.now(UTC)
        row.last_state_check_result = state
        if state in {"removed", "expired", "not_found"}:
            reason = "not_found" if state == "not_found" else "deleted" if state == "removed" else state
            archived += await deactivate_source_record(session, row, reason)
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
            if row.consecutive_unknown_state_runs >= 2:
                archived += await deactivate_source_record(session, row, "source_removed")
        await session.commit()
    return archived


async def run_removal_check(session: AsyncSession, source: ExternalListingSource) -> int:
    """Lightweight safety check; it never performs discovery or image imports."""
    cutoff = datetime.now(UTC) - timedelta(seconds=get_settings().external_removal_check_interval_seconds)
    candidates = (
        await session.execute(
            select(SourceRecord.id, SourceRecord.source_url).where(
                SourceRecord.source_name == source.name,
                SourceRecord.current_status.in_(("active", "missing")),
                SourceRecord.last_checked_at < cutoff,
            ).limit(50)
        )
    ).all()
    await session.commit()

    archived = 0
    for row_id, source_url in candidates:
        require_no_active_transaction(session, "external removal state check")
        state = await source.check_listing_state(source_url)
        row = await session.get(SourceRecord, row_id)
        if not row or row.source_name != source.name or row.current_status not in {"active", "missing"}:
            await session.commit()
            continue
        row.last_checked_at = datetime.now(UTC)
        row.last_state_check_at = row.last_checked_at
        row.last_state_check_result = state
        if state in {"removed", "expired", "not_found"}:
            reason = "not_found" if state == "not_found" else "deleted" if state == "removed" else state
            archived += await deactivate_source_record(session, row, reason)
        elif state == "active":
            was_missing = row.current_status != "active"
            row.current_status = "active"
            row.last_seen_at = datetime.now(UTC)
            row.last_success_at = datetime.now(UTC)
            row.consecutive_missing_runs = 0
            row.consecutive_unknown_state_runs = 0
            row.removed_at = None
            row.removed_reason = None
            row.last_error = None
            if was_missing:
                # Reuse the stored normalized source snapshot: a lightweight
                # removal probe must not re-fetch images merely to restore a
                # reappearing detail page.
                await promote_best_active_source(session, row.canonical_listing_id)
        elif state in {"blocked", "temporary_error"}:
            row.last_error = state
        await session.commit()
    return archived


async def archive_confirmed_not_found(session: AsyncSession, source_name: str, source_url: str) -> int:
    """Compatibility wrapper for detail fetches that already proved a 404."""
    row = await session.scalar(
        select(SourceRecord).where(SourceRecord.source_name == source_name, SourceRecord.source_url == source_url)
    )
    if not row:
        return 0
    row.last_state_check_at = datetime.now(UTC)
    row.last_state_check_result = "not_found"
    return await deactivate_source_record(session, row, "not_found")


async def deactivate_rejected_source(session: AsyncSession, source_name: str, source_url: str) -> None:
    """Do not keep an already imported record visible after strict room validation rejects it."""
    row = await session.scalar(
        select(SourceRecord).where(SourceRecord.source_name == source_name, SourceRecord.source_url == source_url)
    )
    if not row:
        return
    await deactivate_source_record(session, row, "rejected")


async def run_source(session: AsyncSession, source: ExternalListingSource, run_id: str) -> dict[str, int]:
    started = perf_counter()
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
            "filtered_wrong_location",
            "rejected_wrong_location",
            "accepted_rooms",
            "archived",
            "failed",
            "failed_details",
            "rejected_invalid_price",
        )
    })
    run = ExternalImportRun(run_id=run_id, source_name=source.name)
    session.add(run)
    await session.commit()
    started_at = datetime.now(UTC)
    previous_block = await session.scalar(
        select(ExternalImportRun)
        .where(
            ExternalImportRun.source_name == source.name,
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
        previous_success = await session.scalar(
            select(ExternalImportRun)
            .where(
                ExternalImportRun.source_name == source.name,
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
            return counters
        source.not_found_urls.clear()
        getattr(source, "removed_urls", set()).clear()
        if urls:
            rows = await session.scalars(
                select(SourceRecord).where(SourceRecord.source_name == source.name, SourceRecord.source_url.in_(urls))
            )
            known_urls = set()
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
        fetched_results = await asyncio.gather(*(fetch(url) for url in urls), return_exceptions=True)
        partial = False
        for result in fetched_results:
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
                        counters["archived"] += await deactivate_source_record(session, removed_record, "deleted")
                await session.commit()
                continue
            counters["fetched"] += 1
            counters["fetched_details"] += 1
            parsed = source.parse_listing(document, url)
            if not (is_room_offer(parsed) and is_rental(parsed)):
                counters["filtered_not_room"] += 1
                counters["rejected_not_room"] += 1
                await deactivate_rejected_source(session, source.name, url)
                await session.commit()
                continue
            if not is_in_target_province(parsed):
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
            counters["accepted_rooms"] += 1
            outcome = await upsert(session, item)
            counters[outcome] += 1
            if outcome == "imported":
                counters["created"] += 1
        await session.commit()
        if discovery.complete and not partial:
            counters["archived"] += await archive_missing(session, source, started_at)
        run.result = "partial" if partial or not discovery.complete else "success"
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
