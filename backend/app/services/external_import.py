from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import unicodedata
from datetime import UTC, datetime
from io import BytesIO
from time import perf_counter

import httpx
from fastapi import HTTPException
from PIL import Image
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.v1.uploads import validate_and_normalize
from ..core.config import get_settings
from ..core.observability import EXTERNAL_IMPORT_DURATION, EXTERNAL_IMPORTS
from ..external_sources import ExternalListingSource, NormalizedListing
from ..models import ExternalImportRun, Listing, ListingImage, MediaAsset, User
from ..models import ExternalListingSource as SourceRecord
from ..repositories.listings import point
from ..storage import get_storage

logger = logging.getLogger(__name__)
SYSTEM_EMAIL = "external-import@112233.es"
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
        pixels = list(image.convert("L").resize((8, 8)).getdata())
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
                normalized, _, _ = validate_and_normalize(response.content)
                result.add(perceptual_hash(normalized))
            except (HTTPException, OSError, ValueError, httpx.HTTPError):
                continue
    return result


async def import_images(session: AsyncSession, listing: Listing, owner: User, urls: list[str]) -> None:
    """Persist public images where possible; keep source URLs as a safe fallback."""
    if not get_settings().external_import_download_images or not urls:
        return
    attached = set(
        (await session.scalars(select(ListingImage.media_asset_id).where(ListingImage.listing_id == listing.id))).all()
    )
    async with httpx.AsyncClient(
        timeout=get_settings().external_import_request_timeout_seconds, follow_redirects=True
    ) as client:
        for order, url in enumerate(urls[:20]):
            try:
                response = await client.get(url, headers={"User-Agent": get_settings().external_import_user_agent})
                content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                if (
                    response.status_code != 200
                    or not content_type.startswith("image/")
                    or len(response.content) > get_settings().max_upload_bytes
                ):
                    continue
                normalized, width, height = validate_and_normalize(response.content)
                checksum = hashlib.sha256(normalized).hexdigest()
                asset = await session.scalar(
                    select(MediaAsset).where(MediaAsset.checksum == checksum, MediaAsset.deleted_at.is_(None))
                )
                if not asset:
                    asset = MediaAsset(
                        owner_id=owner.id,
                        storage_key=f"external/{checksum}.webp",
                        mime_type="image/webp",
                        size_bytes=len(normalized),
                        width=width,
                        height=height,
                        checksum=checksum,
                        perceptual_hash=perceptual_hash(normalized),
                        kind="listing_image",
                    )
                    await asyncio.to_thread(get_storage().put, asset.storage_key, normalized)
                    session.add(asset)
                    await session.flush()
                if asset.id not in attached:
                    session.add(
                        ListingImage(
                            listing_id=listing.id, media_asset_id=asset.id, sort_order=order, is_cover=order == 0
                        )
                    )
                    attached.add(asset.id)
            except (HTTPException, OSError, ValueError, httpx.HTTPError):
                logger.info("external_image_skipped", extra={"listing_id": str(listing.id), "url": url})


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


async def upsert(session: AsyncSession, item: NormalizedListing) -> str:
    now = datetime.now(UTC)
    source = await session.scalar(
        select(SourceRecord).where(
            SourceRecord.source_name == item.source_name, SourceRecord.external_id == item.external_id
        )
    )
    listing = (
        await session.get(Listing, source.canonical_listing_id)
        if source
        else await canonical_for(session, item, await public_image_hashes(item.photos))
    )
    if source and source.fingerprint == item.fingerprint:
        source.last_checked_at = source.last_success_at = source.last_seen_at = now
        source.consecutive_missing_runs = 0
        source.current_status = "active"
        return "unchanged"
    owner = await system_user(session)
    coordinates = public_location(item)
    if not listing and coordinates is None:
        # The canonical listing requires a map point; never invent one.
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
            minimum_stay_months=None,
            minimum_nights=None,
            room_type=item.room_type,
            location=point(coordinates[1], coordinates[0]),
            status="published",
            published_at=now,
            is_external=True,
            imported_at=now,
            smoking_allowed=None,
            pets_allowed=None,
            children_allowed=None,
            empadronamiento_allowed=None,
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
        await import_images(session, listing, owner, item.photos)
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
            fingerprint=item.fingerprint,
        )
        session.add(source)
    source.raw_payload = item.raw_payload
    source.fingerprint = item.fingerprint
    source.source_url = item.source_url
    source.source_price_text = item.source_price_text
    source.last_checked_at = source.last_success_at = source.last_seen_at = source.content_updated_at = now
    source.consecutive_missing_runs = 0
    source.current_status = "active"
    source.last_error = None
    return "restored" if restored else action


async def archive_missing(session: AsyncSession, source_name: str, started_at: datetime) -> int:
    rows = (
        await session.scalars(
            select(SourceRecord).where(
                SourceRecord.source_name == source_name,
                SourceRecord.current_status == "active",
                SourceRecord.last_seen_at < started_at,
            )
        )
    ).all()
    archived = 0
    for row in rows:
        row.consecutive_missing_runs += 1
        if row.consecutive_missing_runs >= 2:
            row.current_status = "missing"
            listing = await session.get(Listing, row.canonical_listing_id)
            if listing and listing.primary_source == source_name:
                alternatives = await session.scalar(
                    select(SourceRecord).where(
                        SourceRecord.canonical_listing_id == listing.id,
                        SourceRecord.current_status == "active",
                        SourceRecord.source_name != source_name,
                    )
                )
                if alternatives:
                    listing.primary_source = alternatives.source_name
                    listing.primary_source_url = alternatives.source_url
                else:
                    listing.status = "closed"
                    archived += 1
    return archived


async def archive_confirmed_not_found(session: AsyncSession, source_name: str, source_url: str) -> int:
    """Archive a source immediately only after its public detail URL answered HTTP 404."""
    row = await session.scalar(
        select(SourceRecord).where(SourceRecord.source_name == source_name, SourceRecord.source_url == source_url)
    )
    if not row or row.current_status != "active":
        return 0
    row.current_status = "missing"
    row.consecutive_missing_runs = max(row.consecutive_missing_runs, 2)
    listing = await session.get(Listing, row.canonical_listing_id)
    if not listing or listing.primary_source != source_name:
        return 0
    alternative = await session.scalar(
        select(SourceRecord).where(
            SourceRecord.canonical_listing_id == listing.id,
            SourceRecord.current_status == "active",
            SourceRecord.source_name != source_name,
        )
    )
    if alternative:
        listing.primary_source = alternative.source_name
        listing.primary_source_url = alternative.source_url
        return 0
    listing.status = "closed"
    return 1


async def run_source(session: AsyncSession, source: ExternalListingSource, run_id: str) -> dict[str, int]:
    started = perf_counter()
    counters = {
        key: 0
        for key in (
            "discovered",
            "fetched",
            "imported",
            "updated",
            "unchanged",
            "restored",
            "filtered_not_room",
            "filtered_wrong_location",
            "archived",
            "failed",
        )
    }
    run = ExternalImportRun(run_id=run_id, source_name=source.name)
    session.add(run)
    await session.commit()
    started_at = datetime.now(UTC)
    try:
        urls = await source.discover_listing_urls()
        counters["discovered"] = len(urls)
        source.not_found_urls.clear()
        semaphore = asyncio.Semaphore(get_settings().external_import_max_concurrency_per_source)

        async def fetch(url: str):
            async with semaphore:
                return url, await source.fetch_listing(url)

        for url, document in await asyncio.gather(*(fetch(url) for url in urls)):
            if not document:
                if url in source.not_found_urls:
                    counters["archived"] += await archive_confirmed_not_found(session, source.name, url)
                continue
            counters["fetched"] += 1
            item = source.normalize_listing(source.parse_listing(document, url), url)
            if not item:
                counters["filtered_not_room"] += 1
                continue
            counters[await upsert(session, item)] += 1
        counters["archived"] = await archive_missing(session, source.name, started_at)
        run.result = "success"
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
    return counters
