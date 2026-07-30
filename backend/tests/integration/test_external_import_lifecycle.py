from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.external_sources import DiscoveryResult, NormalizedListing, SourceBlocked
from app.models import ExternalImportRun, ExternalListingSource, Listing
from app.services.external_import import archive_missing, run_source, upsert

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


async def test_external_upsert_is_idempotent_deduplicates_and_fails_over_primary_source(client: AsyncClient):
    async with SessionLocal() as session:
        idealista = external_item(
            source="Idealista",
            external_id="idealista-1",
            url="https://www.idealista.com/inmueble/100001/",
        )
        assert await upsert(session, idealista) == "imported"
        await session.commit()
        assert await upsert(session, idealista) == "unchanged"
        await session.commit()

        fotocasa = external_item(
            source="Fotocasa",
            external_id="fotocasa-1",
            url="https://www.fotocasa.es/es/alquiler/inmueble/100001",
            price=740,
        )
        assert await upsert(session, fotocasa) == "updated"
        await session.commit()

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
        visible = await client.post("/api/v1/listings/search", json={"city": "Adeje", "limit": 20})
        assert any(row["id"] for row in visible.json()["items"])
