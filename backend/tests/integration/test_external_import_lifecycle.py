from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.external_sources import DiscoveryResult, NormalizedListing, SourceBlocked
from app.models import ExternalImportRun, ExternalListingSource, Listing
from app.services.external_import import (
    archive_missing,
    deactivate_source_record,
    run_removal_check,
    run_source,
    upsert,
)

pytestmark = pytest.mark.integration


def external_item(*, source: str, external_id: str, url: str, price: int = 710) -> NormalizedListing:
    return NormalizedListing(
        source_name=source,
        external_id=external_id,
        source_url=url,
        title="Habitación exterior cerca de la playa",
        description="Habitación individual amueblada en piso compartido en Adeje.",
        city="Adeje",
        area="Adeje",
        rental_mode="long",
        source_price_text=f"{price} €/mes",
        price_amount=price,
        price_currency="EUR",
        price_period="month",
        price_is_from=False,
        latitude=28.1227,
        longitude=-16.7244,
        phone="+34 612 345 678",
        whatsapp="+34 612 345 678",
        email="owner@example.test",
        raw_payload={"fixture": source},
    )


class FailingSource:
    name = "Idealista"

    async def discover_listing_urls(self) -> list[str]:
        raise RuntimeError("public source unavailable")

    async def close(self) -> None:
        return None


class PartiallyFailingSource:
    name = "Fotocasa"

    def __init__(self) -> None:
        self.not_found_urls: set[str] = set()
        self.blocked_diagnostic = None

    async def discover_listing_urls(self) -> list[str]:
        return ["https://example.test/failing", "https://example.test/working"]

    async def fetch_listing(self, url: str) -> str:
        if url.endswith("failing"):
            raise RuntimeError("temporary detail error")
        return "working"

    def parse_listing(self, document: str, url: str) -> dict:
        return {
            "title": "Habitación individual en alquiler",
            "description": "Se alquila habitación en piso compartido",
            "category": "alquiler habitación",
            "breadcrumbs": "Adeje, Santa Cruz de Tenerife",
            "price_text": "710 €/mes",
        }

    def normalize_listing(self, data: dict, url: str) -> NormalizedListing:
        return external_item(source=self.name, external_id="working", url=url)

    async def close(self) -> None:
        return None


class BlockedSource:
    name = "Milanuncios"

    def __init__(self) -> None:
        self.not_found_urls: set[str] = set()
        self.blocked_diagnostic = {
            "challenge_type": "geetest",
            "status": 403,
            "final_url": "https://example.test/blocked",
            "paths": {"html": "var/error.html", "screenshot": "var/error.png"},
        }

    async def discover_listing_urls(self) -> list[str]:
        raise SourceBlocked("public source access challenge")

    async def close(self) -> None:
        return None


class IncompleteDiscoverySource(PartiallyFailingSource):
    async def discover_listing_urls(self) -> DiscoveryResult:
        return DiscoveryResult(urls=set(), complete=False, visited_pages=1, failed_pages=["https://example.test/page/2"])


class EmptyDiscoverySource(PartiallyFailingSource):
    async def discover_listing_urls(self) -> DiscoveryResult:
        return DiscoveryResult(urls=set(), complete=True, visited_pages=1, reached_last_page=True)


class MissingDetailSource:
    """A complete discovery with an injected detail-state response."""

    def __init__(self, name: str, state: str) -> None:
        self.name = name
        self.state = state
        self.not_found_urls: set[str] = set()
        self.blocked_diagnostic = None

    async def discover_listing_urls(self) -> DiscoveryResult:
        return DiscoveryResult(urls=set(), complete=True, visited_pages=1, reached_last_page=True)

    async def check_listing_state(self, source_url: str) -> str:
        return self.state

    async def close(self) -> None:
        return None


class DirectlyRemovedDetailSource(MissingDetailSource):
    """Models a detail request that explicitly returned HTTP 410/removed."""

    def __init__(self, name: str, url: str) -> None:
        super().__init__(name, "removed")
        self.url = url
        self.removed_urls: set[str] = set()

    async def discover_listing_urls(self) -> DiscoveryResult:
        return DiscoveryResult(urls={self.url}, complete=True, visited_pages=1, reached_last_page=True)

    async def fetch_listing(self, url: str) -> None:
        self.removed_urls.add(url)


async def test_external_upsert_is_idempotent_deduplicates_and_fails_over_primary_source(client: AsyncClient):
    before_catalog = await client.get("/api/v1/listings/catalog-version")
    assert before_catalog.status_code == 200, before_catalog.text
    before_version = int(before_catalog.json()["version"])

    async with SessionLocal() as session:
        idealista = external_item(
            source="Idealista",
            external_id="idealista-1",
            url="https://www.idealista.com/inmueble/100001/",
        )
        assert await upsert(session, idealista) == "imported"
        await session.commit()
        after_import_catalog = await client.get("/api/v1/listings/catalog-version")
        assert after_import_catalog.status_code == 200, after_import_catalog.text
        after_import_version = int(after_import_catalog.json()["version"])
        assert after_import_version > before_version

        assert await upsert(session, idealista) == "unchanged"
        await session.commit()

        source_record = await session.scalar(
            select(ExternalListingSource).where(ExternalListingSource.external_id == "idealista-1")
        )
        assert source_record is not None
        assert source_record.normalized_payload["external_id"] == "idealista-1"
        assert source_record.last_discovered_at is not None

        fotocasa = external_item(
            source="Fotocasa",
            external_id="fotocasa-1",
            url="https://www.fotocasa.es/es/alquiler/inmueble/100001",
            price=740,
        )
        assert await upsert(session, fotocasa) == "updated"
        await session.commit()
        after_update_catalog = await client.get("/api/v1/listings/catalog-version")
        assert after_update_catalog.status_code == 200, after_update_catalog.text
        after_update_version = int(after_update_catalog.json()["version"])
        assert after_update_version > after_import_version

        assert await session.scalar(select(func.count()).select_from(Listing).where(Listing.is_external.is_(True))) == 1
        assert await session.scalar(select(func.count()).select_from(ExternalListingSource)) == 2
        listing = await session.scalar(select(Listing).where(Listing.is_external.is_(True)))
        assert listing is not None and listing.source_price_text == "740 €/mes"

        search = await client.post("/api/v1/listings/search", json={"city": "Adeje", "limit": 20})
        assert search.status_code == 200, search.text
        external = next(item for item in search.json()["items"] if item["id"] == str(listing.id))
        assert external["isExternal"] is True
        assert external["sourceUrl"] == fotocasa.source_url
        assert external["sourcePriceText"] == "740 €/mes"

        future_run = datetime.now(UTC) + timedelta(minutes=1)
        assert await archive_missing(session, "Fotocasa", future_run) == 0
        assert await archive_missing(session, "Fotocasa", future_run) == 0
        await session.commit()
        await session.refresh(listing)
        assert listing.status == "published"
        assert listing.primary_source == "Idealista"

        assert await archive_missing(session, "Idealista", future_run) == 0
        assert await archive_missing(session, "Idealista", future_run) == 1
        await session.commit()
        await session.refresh(listing)
        assert listing.status == "closed"

        closed_catalog = await client.get("/api/v1/listings/catalog-version")
        assert closed_catalog.status_code == 200, closed_catalog.text
        assert int(closed_catalog.json()["version"]) > after_update_version

        hidden = await client.post("/api/v1/listings/search", json={"city": "Adeje", "limit": 20})
        assert hidden.status_code == 200, hidden.text
        assert all(item["id"] != str(listing.id) for item in hidden.json()["items"])


async def test_complete_source_failure_does_not_mark_existing_external_listing_missing():
    async with SessionLocal() as session:
        item = external_item(
            source="Idealista",
            external_id="idealista-2",
            url="https://www.idealista.com/inmueble/100002/",
        )
        assert await upsert(session, item) == "imported"
        await session.commit()

        counters = await run_source(session, FailingSource(), "test-failing-source")  # type: ignore[arg-type]
        assert counters["failed"] == 1
        source = await session.scalar(
            select(ExternalListingSource).where(ExternalListingSource.external_id == "idealista-2")
        )
        assert source is not None
        assert source.current_status == "active"
        assert source.consecutive_missing_runs == 0


async def test_detail_error_is_partial_and_blocked_source_records_diagnostics():
    async with SessionLocal() as session:
        partial = await run_source(session, PartiallyFailingSource(), "test-partial")  # type: ignore[arg-type]
        assert partial["failed_details"] == 1
        run = await session.scalar(select(ExternalImportRun).where(ExternalImportRun.run_id == "test-partial"))
        assert run is not None and run.result == "partial"

        blocked = await run_source(session, BlockedSource(), "test-blocked")  # type: ignore[arg-type]
        assert blocked["failed"] == 1
        blocked_run = await session.scalar(select(ExternalImportRun).where(ExternalImportRun.run_id == "test-blocked"))
        assert blocked_run is not None
        assert blocked_run.result == "blocked"
        assert blocked_run.challenge_type == "geetest"
        assert blocked_run.http_status == 403
        assert blocked_run.next_check_at is not None


async def test_incomplete_discovery_does_not_archive_active_source_or_catalog_entry(client: AsyncClient):
    async with SessionLocal() as session:
        item = external_item(source="Fotocasa", external_id="incomplete-1", url="https://example.test/incomplete")
        assert await upsert(session, item) == "imported"
        await session.commit()
        before = await client.get("/api/v1/listings/catalog-version")
        assert before.status_code == 200
        counters = await run_source(session, IncompleteDiscoverySource(), "test-incomplete")  # type: ignore[arg-type]
        await session.commit()
        record = await session.scalar(select(ExternalListingSource).where(ExternalListingSource.external_id == "incomplete-1"))
        run = await session.scalar(select(ExternalImportRun).where(ExternalImportRun.run_id == "test-incomplete"))
        assert counters["archived"] == 0
        assert record is not None and record.current_status == "active" and record.consecutive_missing_runs == 0
        assert run is not None and run.result == "partial" and run.discovery_complete is False
        after = await client.get("/api/v1/listings/catalog-version")
        assert after.status_code == 200
        assert after.json()["version"] == before.json()["version"]
        visible = await client.post("/api/v1/listings/search", json={"city": "Adeje", "limit": 20})
        assert any(row["id"] for row in visible.json()["items"])


async def test_sudden_drop_to_zero_urls_is_partial_and_never_archives_existing_source():
    async with SessionLocal() as session:
        item = external_item(source="Fotocasa", external_id="volume-drop", url="https://example.test/volume-drop")
        assert await upsert(session, item) == "imported"
        session.add(
            ExternalImportRun(
                run_id="previous-volume",
                source_name="Fotocasa",
                result="success",
                finished_at=datetime.now(UTC),
                counters={"discovered_urls": 10},
            )
        )
        await session.commit()
        counters = await run_source(session, EmptyDiscoverySource(), "volume-drop")  # type: ignore[arg-type]
        record = await session.scalar(select(ExternalListingSource).where(ExternalListingSource.external_id == "volume-drop"))
        run = await session.scalar(select(ExternalImportRun).where(ExternalImportRun.run_id == "volume-drop"))
        assert counters["archived"] == 0
        assert record is not None and record.current_status == "active"
        assert run is not None and run.result == "partial" and run.discovery_complete is False


@pytest.mark.parametrize("state", ["not_found", "removed", "expired"])
async def test_confirmed_missing_detail_hides_listing_in_same_complete_cycle(client: AsyncClient, state: str):
    async with SessionLocal() as session:
        item = external_item(source="PisoCompartido", external_id=f"removed-{state}", url=f"https://example.test/{state}")
        assert await upsert(session, item) == "imported"
        await session.commit()

        counters = await run_source(session, MissingDetailSource("PisoCompartido", state), f"removed-{state}")  # type: ignore[arg-type]
        assert counters["archived"] == 1
        record = await session.scalar(select(ExternalListingSource).where(ExternalListingSource.external_id == f"removed-{state}"))
        listing = await session.get(Listing, record.canonical_listing_id) if record else None
        expected_reason = "deleted" if state == "removed" else state
        assert record is not None and record.current_status == "missing" and record.removed_reason == expected_reason
        assert listing is not None and listing.status == "closed"

        public = await client.post("/api/v1/listings/search", json={"city": "Adeje", "limit": 20})
        assert all(row["id"] != str(listing.id) for row in public.json()["items"])


async def test_410_returned_while_fetching_discovered_detail_closes_listing_immediately():
    async with SessionLocal() as session:
        url = "https://example.test/direct-410"
        item = external_item(source="Idealista", external_id="direct-410", url=url)
        assert await upsert(session, item) == "imported"
        await session.commit()

        counters = await run_source(session, DirectlyRemovedDetailSource("Idealista", url), "direct-410")  # type: ignore[arg-type]
        record = await session.scalar(select(ExternalListingSource).where(ExternalListingSource.external_id == "direct-410"))
        listing = await session.get(Listing, record.canonical_listing_id) if record else None
        assert counters["archived"] == 1
        assert record is not None and record.current_status == "missing" and record.removed_reason == "deleted"
        assert listing is not None and listing.status == "closed"


@pytest.mark.parametrize("state", ["blocked", "temporary_error", "unknown"])
async def test_ambiguous_missing_detail_keeps_listing_published(state: str):
    async with SessionLocal() as session:
        item = external_item(source="Milanuncios", external_id=f"transient-{state}", url=f"https://example.test/{state}")
        assert await upsert(session, item) == "imported"
        await session.commit()

        counters = await run_source(session, MissingDetailSource("Milanuncios", state), f"transient-{state}")  # type: ignore[arg-type]
        record = await session.scalar(select(ExternalListingSource).where(ExternalListingSource.external_id == f"transient-{state}"))
        listing = await session.get(Listing, record.canonical_listing_id) if record else None
        assert counters["archived"] == 0
        expected_unknown_runs = 1 if state == "unknown" else 0
        assert record is not None and record.current_status == "active" and record.consecutive_missing_runs == 0
        assert record.consecutive_unknown_state_runs == expected_unknown_runs
        assert listing is not None and listing.status == "published"


async def test_primary_removal_promotes_full_alternative_snapshot_and_restores_reappearing_source():
    async with SessionLocal() as session:
        primary = external_item(
            source="Idealista",
            external_id="primary-source",
            url="https://example.test/primary-source",
            price=710,
        )
        primary.photos = []
        assert await upsert(session, primary) == "imported"
        await session.commit()

        alternative = external_item(
            source="Fotocasa",
            external_id="alternative-source",
            url="https://example.test/alternative-source",
            price=680,
        )
        alternative.title = "Alternative room in Adeje"
        alternative.description = "Alternative source description"
        # Do not make an actual remote image request from the lifecycle test;
        # inject the already-normalized source snapshot below instead.
        alternative.photos = []
        alternative.phone = "+34 611 000 000"
        alternative.whatsapp = None
        alternative.email = "alternative@example.test"
        # Share one public contact only to deliberately exercise canonical deduplication.
        alternative.raw_payload = {"fixture": "Fotocasa", "shared": primary.phone}
        alternative.email = primary.email
        assert await upsert(session, alternative) == "updated"
        await session.commit()

        alternative.photos = ["https://images.example.test/alternative.jpg"]
        alternative_record = await session.scalar(
            select(ExternalListingSource).where(ExternalListingSource.external_id == "alternative-source")
        )
        assert alternative_record is not None
        alternative_record.normalized_payload = {
            **alternative_record.normalized_payload,
            "photos": alternative.photos,
        }
        await session.commit()

        source = await session.scalar(select(ExternalListingSource).where(ExternalListingSource.external_id == "primary-source"))
        assert source is not None
        assert await deactivate_source_record(session, source, "removed") == 0
        await session.commit()

        listing = await session.get(Listing, source.canonical_listing_id)
        assert listing is not None and listing.status == "published"
        assert listing.primary_source == "Fotocasa"
        assert listing.primary_source_url == alternative.source_url
        assert listing.source_price_text == alternative.source_price_text
        assert listing.external_image_urls == alternative.photos
        assert listing.external_contact_email == alternative.email

        # The returned URL has the same content as before, but must reopen the
        # canonical card after its only source was closed in a later cycle.
        await deactivate_source_record(session, await session.scalar(select(ExternalListingSource).where(ExternalListingSource.external_id == "alternative-source")), "removed")  # type: ignore[arg-type]
        await session.commit()
        assert listing.status == "closed"
        assert await upsert(session, alternative) == "restored"
        await session.commit()
        await session.refresh(listing)
        assert listing.status == "published"


async def test_removal_checker_restores_previously_missing_source():
    async with SessionLocal() as session:
        item = external_item(source="PisoCompartido", external_id="checker-restore", url="https://example.test/checker-restore")
        assert await upsert(session, item) == "imported"
        await session.commit()
        record = await session.scalar(select(ExternalListingSource).where(ExternalListingSource.external_id == "checker-restore"))
        assert record is not None
        assert await deactivate_source_record(session, record, "deleted") == 1
        await session.commit()

        # Ensure the stored record qualifies as stale for the lightweight run.
        record.last_checked_at = datetime.now(UTC) - timedelta(hours=1)
        await session.commit()
        source = MissingDetailSource("PisoCompartido", "active")
        assert await run_removal_check(session, source) == 0  # type: ignore[arg-type]
        await session.commit()
        await session.refresh(record)
        listing = await session.get(Listing, record.canonical_listing_id)
        assert record.current_status == "active"
        assert listing is not None and listing.status == "published"


async def test_catalog_version_changes_for_create_close_and_restore(client: AsyncClient):
    async with SessionLocal() as session:
        initial = await client.get("/api/v1/listings/catalog-version")
        assert initial.status_code == 200
        initial_version = int(initial.json()["version"])

        item = external_item(source="Fotocasa", external_id="catalog-version", url="https://example.test/catalog-version")
        assert await upsert(session, item) == "imported"
        await session.commit()
        created_version = int((await client.get("/api/v1/listings/catalog-version")).json()["version"])
        assert created_version > initial_version

        record = await session.scalar(select(ExternalListingSource).where(ExternalListingSource.external_id == "catalog-version"))
        assert record is not None
        assert await deactivate_source_record(session, record, "removed") == 1
        await session.commit()
        closed_version = int((await client.get("/api/v1/listings/catalog-version")).json()["version"])
        assert closed_version > created_version

        assert await upsert(session, item) == "restored"
        await session.commit()
        restored_version = int((await client.get("/api/v1/listings/catalog-version")).json()["version"])
        assert restored_version > closed_version


async def test_public_search_returns_all_records_across_multiple_api_pages(client: AsyncClient):
    """Guard the 100-record API boundary used by the browser catalog client."""
    expected_ids: set[str] = set()
    async with SessionLocal() as session:
        for index in range(150):
            item = external_item(
                source="PaginationSource",
                external_id=f"page-{index}",
                url=f"https://example.test/pagination/{index}",
                price=500 + index,
            )
            item.title = f"Pagination listing {index}"
            item.phone = f"+34 600 {index:03d} {index:03d}"
            item.whatsapp = item.phone
            item.email = f"pagination-{index}@example.test"
            assert await upsert(session, item) == "imported"

        rows = await session.scalars(
            select(Listing.id).where(Listing.is_external.is_(True), Listing.primary_source == "PaginationSource")
        )
        expected_ids = {str(listing_id) for listing_id in rows}

    assert len(expected_ids) == 150
    first = await client.post("/api/v1/listings/search", json={"rentalMode": "long", "limit": 100, "offset": 0})
    second = await client.post("/api/v1/listings/search", json={"rentalMode": "long", "limit": 100, "offset": 100})
    assert first.status_code == second.status_code == 200
    assert first.json()["total"] == second.json()["total"] == 150
    assert first.json()["limit"] == second.json()["limit"] == 100
    assert first.json()["offset"] == 0
    assert second.json()["offset"] == 100

    returned_ids = [item["id"] for item in first.json()["items"] + second.json()["items"]]
    assert len(returned_ids) == 150
    assert len(set(returned_ids)) == 150
    assert set(returned_ids) == expected_ids
