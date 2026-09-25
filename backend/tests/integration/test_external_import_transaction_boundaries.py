from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest
from PIL import Image
from botocore.exceptions import EndpointConnectionError
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.external_sources import DiscoveryResult, NormalizedListing
from app.models import ExternalListingSource, Listing, ListingImage, MediaAsset, User
from app.services import external_import as importer

pytestmark = pytest.mark.integration


def external_item(*, source: str, external_id: str, url: str, photos: list[str] | None = None) -> NormalizedListing:
    return NormalizedListing(
        source_name=source,
        external_id=external_id,
        source_url=url,
        title="Habitación exterior cerca de la playa",
        description="Habitación individual amueblada en piso compartido en Adeje.",
        city="Adeje",
        area="Adeje",
        rental_mode="long",
        source_price_text="710 €/mes",
        price_amount=710,
        price_currency="EUR",
        price_period="month",
        price_is_from=False,
        latitude=28.1227,
        longitude=-16.7244,
        photos=photos or [],
        raw_payload={"fixture": source},
    )


class TransactionCheckingSource:
    name = "Pisos"

    def __init__(self, session) -> None:
        self.session = session
        self.not_found_urls: set[str] = set()
        self.removed_urls: set[str] = set()
        self.blocked_diagnostic = None
        self.discovery_checked = False
        self.fetch_checked = False

    async def discover_listing_urls(self) -> DiscoveryResult:
        assert not self.session.in_transaction()
        self.discovery_checked = True
        return DiscoveryResult(
            urls={"https://www.pisos.com/alquiler/habitacion-transaction-boundary/"},
            complete=True,
            visited_pages=1,
            reached_last_page=True,
        )

    async def fetch_listing(self, url: str) -> str:
        assert not self.session.in_transaction()
        self.fetch_checked = True
        return "detail"

    def parse_listing(self, document: str, url: str) -> dict:
        return {
            "title": "Habitación individual en alquiler",
            "description": "Se alquila habitación en piso compartido",
            "category": "alquiler habitación",
            "breadcrumbs": "Adeje, Santa Cruz de Tenerife",
            "price_text": "710 €/mes",
        }

    def normalize_listing(self, data: dict, url: str) -> NormalizedListing:
        return external_item(source=self.name, external_id="transaction-boundary", url=url)

    async def close(self) -> None:
        return None


class ProbeSource:
    name = "PisoCompartido"

    def __init__(self, session) -> None:
        self.session = session
        self.calls = 0

    async def check_listing_state(self, source_url: str) -> str:
        assert not self.session.in_transaction()
        self.calls += 1
        return "active"


class FailingS3Storage:
    def put(self, key: str, content: bytes) -> None:
        raise EndpointConnectionError(endpoint_url="http://minio:9000")

    def delete(self, key: str) -> None:
        raise EndpointConnectionError(endpoint_url="http://minio:9000")


class RecordingStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, content: bytes) -> None:
        self.objects[key] = content

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


async def test_source_discovery_and_detail_fetch_run_without_database_transaction(monkeypatch):
    async with SessionLocal() as session:
        source = TransactionCheckingSource(session)

        async def no_image_hashes(urls: list[str]) -> list:
            assert not session.in_transaction()
            return []

        monkeypatch.setattr(importer, "public_image_fingerprints", no_image_hashes)
        counters = await importer.run_source(session, source, "transaction-boundary-run")  # type: ignore[arg-type]

        assert counters.result == "success"
        assert counters["imported"] == 1
        assert source.discovery_checked
        assert source.fetch_checked
        assert not session.in_transaction()


async def test_public_image_fingerprints_use_full_bounded_gallery_and_fail_closed(monkeypatch):
    calls: list[str] = []

    output = BytesIO()
    Image.new("RGB", (32, 24), (80, 120, 160)).save(output, "PNG")
    image_bytes = output.getvalue()

    class FakeResponse:
        def __init__(self, *, ok: bool = True) -> None:
            self.status_code = 200 if ok else 503
            self.headers = {"content-type": "image/png"}
            self.content = image_bytes

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, headers=None):
            calls.append(url)
            return FakeResponse(ok=not url.endswith("broken.png"))

    monkeypatch.setattr(importer.httpx, "AsyncClient", lambda **kwargs: FakeClient())

    urls = [f"https://images.example.test/sample-{index}.png" for index in range(7)]
    fingerprints = await importer.public_image_fingerprints(urls)
    assert sorted(calls) == sorted(urls)
    assert len(fingerprints) == 7

    calls.clear()
    incomplete = [*urls, "https://images.example.test/broken.png"]
    assert await importer.public_image_fingerprints(incomplete) == []
    assert sorted(calls) == sorted(incomplete)


async def test_image_download_and_storage_do_not_reuse_another_users_private_asset(monkeypatch):
    normalized = b"normalized-external-image"
    checksum = hashlib.sha256(normalized).hexdigest()
    storage = RecordingStorage()

    async with SessionLocal() as session:
        private_owner = User(
            email="private-media-owner@example.test",
            password_hash=None,
            name="Private media owner",
            role="host",
            initials="PM",
            email_verified=True,
        )
        session.add(private_owner)
        await session.flush()
        private_asset = MediaAsset(
            owner_id=private_owner.id,
            storage_key="private/asset.webp",
            mime_type="image/webp",
            size_bytes=len(normalized),
            width=16,
            height=16,
            checksum=checksum,
            perceptual_hash="0" * 16,
            kind="listing_image",
        )
        session.add(private_asset)
        await session.commit()

        async def image_hashes(urls: list[str]) -> list:
            assert not session.in_transaction()
            return []

        async def prepared_image(client, url: str) -> importer.PreparedExternalImage:
            assert not session.in_transaction()
            return importer.PreparedExternalImage(
                content=normalized,
                width=16,
                height=16,
                checksum=checksum,
                perceptual_hash="1" * 16,
            )

        monkeypatch.setattr(importer, "public_image_fingerprints", image_hashes)
        monkeypatch.setattr(importer, "download_external_image", prepared_image)
        monkeypatch.setattr(importer, "get_storage", lambda: storage)

        item = external_item(
            source="Idealista",
            external_id="private-asset-boundary",
            url="https://www.idealista.com/inmueble/private-asset-boundary/",
            photos=["https://images.example.test/room.webp"],
        )
        assert await importer.upsert(session, item) == "imported"
        assert not session.in_transaction()

        source_record = await session.scalar(
            select(ExternalListingSource).where(
                ExternalListingSource.source_name == item.source_name,
                ExternalListingSource.external_id == item.external_id,
            )
        )
        assert source_record is not None
        attached_asset = await session.scalar(
            select(MediaAsset)
            .join(ListingImage, ListingImage.media_asset_id == MediaAsset.id)
            .where(ListingImage.listing_id == source_record.canonical_listing_id)
        )
        system_owner = await session.scalar(select(User).where(User.email == importer.SYSTEM_EMAIL))
        assert attached_asset is not None and system_owner is not None
        assert attached_asset.id != private_asset.id
        assert attached_asset.owner_id == system_owner.id
        assert attached_asset.kind == "listing_image"
        assert storage.objects == {attached_asset.storage_key: normalized}
        assert attached_asset.storage_key.startswith(f"external/{system_owner.id}/")
        assert attached_asset.storage_key.endswith(".webp")


async def test_s3_failure_skips_image_without_aborting_listing_import(monkeypatch):
    normalized = b"unavailable-s3-image"
    checksum = hashlib.sha256(normalized).hexdigest()

    async with SessionLocal() as session:
        async def image_hashes(urls: list[str]) -> list:
            assert not session.in_transaction()
            return []

        async def prepared_image(client, url: str) -> importer.PreparedExternalImage:
            assert not session.in_transaction()
            return importer.PreparedExternalImage(
                content=normalized,
                width=16,
                height=16,
                checksum=checksum,
                perceptual_hash="2" * 16,
            )

        monkeypatch.setattr(importer, "public_image_fingerprints", image_hashes)
        monkeypatch.setattr(importer, "download_external_image", prepared_image)
        monkeypatch.setattr(importer, "get_storage", FailingS3Storage)

        item = external_item(
            source="Idealista",
            external_id="s3-failure-boundary",
            url="https://www.idealista.com/inmueble/s3-failure-boundary/",
            photos=["https://images.example.test/unavailable.webp"],
        )
        assert await importer.upsert(session, item) == "imported"
        assert not session.in_transaction()

        source_record = await session.scalar(
            select(ExternalListingSource).where(
                ExternalListingSource.source_name == item.source_name,
                ExternalListingSource.external_id == item.external_id,
            )
        )
        assert source_record is not None
        attached_count = len(
            (
                await session.scalars(
                    select(ListingImage.media_asset_id).where(
                        ListingImage.listing_id == source_record.canonical_listing_id
                    )
                )
            ).all()
        )
        persisted_asset = await session.scalar(
            select(MediaAsset.id).where(MediaAsset.checksum == checksum)
        )
        assert attached_count == 0
        assert persisted_asset is None


async def test_unchanged_source_retries_deferred_gallery_reconciliation(monkeypatch):
    storage = RecordingStorage()
    attempts = 0

    async with SessionLocal() as session:
        async def no_hashes(urls: list[str]) -> list:
            assert not session.in_transaction()
            return []

        async def flaky_image(client, url: str) -> importer.PreparedExternalImage | None:
            nonlocal attempts
            assert not session.in_transaction()
            attempts += 1
            if attempts == 1:
                return None
            content = b"recovered-gallery-image"
            return importer.PreparedExternalImage(
                content=content,
                width=64,
                height=48,
                checksum=hashlib.sha256(content).hexdigest(),
                perceptual_hash="3" * 16,
            )

        monkeypatch.setattr(importer, "public_image_fingerprints", no_hashes)
        monkeypatch.setattr(importer, "download_external_image", flaky_image)
        monkeypatch.setattr(importer, "get_storage", lambda: storage)

        item = external_item(
            source="Idealista",
            external_id="retry-deferred-gallery",
            url="https://www.idealista.com/inmueble/retry-deferred-gallery/",
            photos=["https://images.example.test/retry.webp"],
        )
        assert await importer.upsert(session, item) == "imported"

        source_record = await session.scalar(
            select(ExternalListingSource).where(
                ExternalListingSource.source_name == item.source_name,
                ExternalListingSource.external_id == item.external_id,
            )
        )
        assert source_record is not None
        first_count = int(
            await session.scalar(
                select(func.count(ListingImage.media_asset_id)).where(
                    ListingImage.listing_id == source_record.canonical_listing_id
                )
            )
            or 0
        )
        assert first_count == 0

        assert await importer.upsert(session, item) == "updated"
        second_count = int(
            await session.scalar(
                select(func.count(ListingImage.media_asset_id)).where(
                    ListingImage.listing_id == source_record.canonical_listing_id
                )
            )
            or 0
        )
        assert second_count == 1
        assert attempts == 2
        assert not session.in_transaction()


async def test_external_gallery_reconciliation_caps_and_replaces_stale_images(monkeypatch):
    storage = RecordingStorage()
    calls: list[str] = []

    async with SessionLocal() as session:
        async def prepared_image(client, url: str) -> importer.PreparedExternalImage:
            assert not session.in_transaction()
            calls.append(url)
            content = f"normalized:{url}".encode()
            return importer.PreparedExternalImage(
                content=content,
                width=64,
                height=48,
                checksum=hashlib.sha256(content).hexdigest(),
                perceptual_hash=hashlib.sha256(f"phash:{url}".encode()).hexdigest()[:16],
            )

        monkeypatch.setattr(importer, "download_external_image", prepared_image)
        monkeypatch.setattr(importer, "get_storage", lambda: storage)

        item = external_item(
            source="Idealista",
            external_id="gallery-reconcile-boundary",
            url="https://www.idealista.com/inmueble/gallery-reconcile-boundary/",
            photos=[],
        )
        assert await importer.upsert(session, item) == "imported"

        source_record = await session.scalar(
            select(ExternalListingSource).where(
                ExternalListingSource.source_name == item.source_name,
                ExternalListingSource.external_id == item.external_id,
            )
        )
        assert source_record is not None
        listing = await session.get(Listing, source_record.canonical_listing_id)
        assert listing is not None

        first_urls = [f"https://images.example.test/room-{index}.webp" for index in range(25)]
        await importer.import_images(session, listing.id, listing.owner_user_id, first_urls)
        assert sorted(calls) == sorted(first_urls[:20])

        first_ids = list(
            (
                await session.scalars(
                    select(ListingImage.media_asset_id)
                    .where(ListingImage.listing_id == listing.id)
                    .order_by(ListingImage.sort_order)
                )
            ).all()
        )
        assert len(first_ids) == 20

        calls.clear()
        replacement_urls = [
            first_urls[5],
            first_urls[7],
            "https://images.example.test/replacement-new.webp",
        ]
        await importer.import_images(session, listing.id, listing.owner_user_id, replacement_urls)
        assert sorted(calls) == sorted(replacement_urls)

        current_assets = list(
            (
                await session.scalars(
                    select(MediaAsset)
                    .join(ListingImage, ListingImage.media_asset_id == MediaAsset.id)
                    .where(ListingImage.listing_id == listing.id)
                    .order_by(ListingImage.sort_order)
                )
            ).all()
        )
        expected_checksums = [
            hashlib.sha256(f"normalized:{url}".encode()).hexdigest()
            for url in replacement_urls
        ]
        assert [asset.checksum for asset in current_assets] == expected_checksums
        assert len(current_assets) == 3

        stale_ids = set(first_ids) - {asset.id for asset in current_assets}
        stale_assets = list(
            (
                await session.scalars(
                    select(MediaAsset).where(MediaAsset.id.in_(stale_ids))
                )
            ).all()
        )
        assert stale_assets
        assert all(asset.deleted_at is not None for asset in stale_assets)
        assert not session.in_transaction()


async def test_reconciliation_probes_run_without_database_transaction(monkeypatch):
    async with SessionLocal() as session:
        item = external_item(
            source="PisoCompartido",
            external_id="probe-boundary",
            url="https://www.pisocompartido.com/habitacion/probe-boundary",
        )
        monkeypatch.setattr(importer, "public_image_fingerprints", lambda urls: _empty_hashes(session))
        assert await importer.upsert(session, item) == "imported"

        record = await session.scalar(
            select(ExternalListingSource).where(ExternalListingSource.external_id == item.external_id)
        )
        assert record is not None
        record.last_seen_at = datetime.now(UTC) - timedelta(hours=2)
        record.last_checked_at = datetime.now(UTC) - timedelta(hours=2)
        await session.commit()

        source = ProbeSource(session)
        assert await importer.archive_missing(session, source, datetime.now(UTC)) == 0  # type: ignore[arg-type]

        record.last_checked_at = datetime.now(UTC) - timedelta(hours=2)
        await session.commit()
        assert await importer.run_removal_check(session, source) == 0  # type: ignore[arg-type]
        assert source.calls == 2
        assert not session.in_transaction()


async def _empty_hashes(session) -> list:
    assert not session.in_transaction()
    return []
