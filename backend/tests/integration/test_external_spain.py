from __future__ import annotations

from argparse import Namespace
from contextlib import asynccontextmanager
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.external_sources import DiscoveryResult, NormalizedListing, PisosSource
from app.models import ExternalImportRun, ExternalImportScope, ExternalListingSource, Listing, ListingImage, MediaAsset
from app.services import external_import
from app.services.external_import import run_source, upsert
from app.services.external_scopes import ScopeDefinition, provision_scopes
from app.services.listing_deduplication import ImageFingerprint

pytestmark = pytest.mark.integration


def item(**changes):
    base = NormalizedListing(
        source_name="Pisos",
        external_id="spain-123456",
        source_url="https://www.pisos.com/alquilar/piso-madrid-123456/",
        title="Piso de 1 dormitorio en alquiler",
        description="Apartamento de un dormitorio para larga estancia.",
        city="Madrid",
        area="Madrid",
        rental_mode="long",
        source_price_text="900 €/mes",
        price_amount=900,
        price_currency="EUR",
        price_period="month",
        price_is_from=False,
        room_type="Apartamento de 1 dormitorio",
        bedroom_count=1,
        province="Madrid",
        country="ES",
        latitude=40.4,
        longitude=-3.7,
    )
    return replace(base, **changes)


async def test_provision_disabled_scopes_upserts_without_duplicate_or_implicit_activation():
    definition = ScopeDefinition("Pisos", "province:Madrid", ("https://www.pisos.com/alquiler/pisos-madrid/",))
    async with SessionLocal() as session:
        await provision_scopes(session, [definition])
        await provision_scopes(session, [definition])
        rows = list((await session.scalars(select(ExternalImportScope))).all())
        assert len(rows) == 1 and not rows[0].enabled
        await provision_scopes(session, [definition], enable=True)
        await provision_scopes(session, [definition])
        await session.refresh(rows[0])
        assert rows[0].enabled


async def test_holiday_scopes_keep_independent_cursors_and_rejected_recommendations_do_not_close_long(monkeypatch):
    monkeypatch.setattr(external_import.get_settings(), "external_import_download_images", False)
    long_root = "https://www.pisos.com/alquiler/pisos-madrid/"
    holiday_root = "https://www.pisos.com/alquiler-vacacional/pisos-madrid/"

    class Source(PisosSource):
        scope_key = "province:Madrid:holiday"
        discovery_urls = (holiday_root,)

        async def discover_listing_urls(self):
            return DiscoveryResult(urls={item().source_url}, complete=False, visited_pages=1)

        async def fetch_listing(self, url):
            return '''<script type="application/ld+json">{"@type":"Apartment","propertyType":"apartment",
              "numberOfBedrooms":1,"name":"Apartamento","description":"Larga estancia","rentalCategory":"residential",
              "address":{"addressLocality":"Madrid","addressRegion":"Madrid","addressCountry":"ES"}}
              </script><p>950 €/mes</p>'''

    async with SessionLocal() as session:
        await provision_scopes(session, [ScopeDefinition("Pisos", "province:Madrid", (long_root,))])
        with pytest.raises(ValueError, match="Holiday import scopes are disabled"):
            await provision_scopes(session, [ScopeDefinition("Pisos", "province:Madrid:holiday", (holiday_root,))])
        assert await upsert(session, item(), scope_key="province:Madrid") == "imported"
        before = await session.scalar(select(ExternalListingSource))
        listing_id = before.canonical_listing_id
        with pytest.raises(ValueError, match="Holiday import scopes are disabled"):
            await run_source(session, Source(), str(uuid4()), max_details=1)
        source = await session.scalar(select(ExternalListingSource))
        listing = await session.get(Listing, listing_id)
        assert source.current_status == "active" and source.scope_key == "province:Madrid"
        assert listing.status == "published" and listing.rental_mode == "long" and listing.monthly_price == 900
        assert await session.scalar(select(func.count(ExternalImportScope.id))) == 1


async def test_holiday_catalogue_overlap_preserves_long_term_canonical_and_its_scope(monkeypatch):
    monkeypatch.setattr(external_import.get_settings(), "external_import_download_images", False)
    async with SessionLocal() as session:
        original = item()
        assert await upsert(session, original, scope_key="province:Madrid") == "imported"
        source = await session.scalar(select(ExternalListingSource))
        listing = await session.get(Listing, source.canonical_listing_id)
        original_source_id = source.id
        original_listing_id = listing.id

        holiday = item(
            rental_mode="holiday",
            source_price_text="490 €/sem",
            price_amount=70,
            price_period="week",
            weekly_price_amount=490,
        )
        result = await upsert(session, holiday, scope_key="province:Madrid:holiday")
        assert result == "policy_rejected"
        await session.refresh(source)
        await session.refresh(listing)
        assert source.id == original_source_id
        assert source.scope_key == "province:Madrid"
        assert listing.id == original_listing_id
        assert listing.rental_mode == "long"
        assert listing.monthly_price == 900 and listing.nightly_price is None
        assert listing.status == "published"
        assert await session.scalar(select(func.count(ExternalListingSource.id))) == 1
        assert await session.scalar(select(func.count(Listing.id))) == 1

        # Ordinary price refreshes from the owning residential scope remain
        # permitted: a changed aggregate checksum is not itself data loss.
        updated = item(price_amount=925, source_price_text="925 €/mes")
        assert await upsert(session, updated, scope_key="province:Madrid") == "updated"
        await session.refresh(listing)
        assert listing.rental_mode == "long" and listing.monthly_price == 925


async def test_residential_import_cannot_take_over_existing_holiday_source(monkeypatch):
    monkeypatch.setattr(external_import.get_settings(), "external_import_download_images", False)
    holiday = item(
        rental_mode="holiday",
        source_price_text="490 €/sem",
        price_amount=70,
        price_period="week",
        weekly_price_amount=490,
    )
    async with SessionLocal() as session:
        assert await upsert(session, holiday, scope_key="province:Madrid:holiday") == "policy_rejected"
        assert await session.scalar(select(ExternalListingSource)) is None
        assert await session.scalar(select(Listing)) is None
        # Rejecting tourism must not poison the same property identity for a later valid residential offer.
        assert await upsert(session, item(), scope_key="province:Madrid") == "imported"
        source = await session.scalar(select(ExternalListingSource))
        listing = await session.get(Listing, source.canonical_listing_id)
        assert source.scope_key == "province:Madrid"
        assert listing.rental_mode == "long" and listing.monthly_price == 900


async def test_selected_holiday_weekly_price_reaches_canonical_and_retains_provenance(monkeypatch):
    monkeypatch.setattr(external_import.get_settings(), "external_import_download_images", False)
    root = "https://www.pisos.com/alquiler-vacacional/pisos-madrid/"

    class Source(PisosSource):
        scope_key = "province:Madrid:holiday"
        discovery_urls = (root,)

        async def discover_listing_urls(self):
            return DiscoveryResult(urls={item().source_url}, complete=False, visited_pages=1)

        async def fetch_listing(self, url):
            return '''<script type="application/ld+json">{"@type":"Apartment","propertyType":"apartment",
              "numberOfBedrooms":1,"name":"Apartamento","description":"Vacacional","rentalCategory":"holiday",
              "address":{"addressLocality":"Madrid","addressRegion":"Madrid","addressCountry":"ES"}}
              </script><div class="jsPriceValue">490 €</div><select class="jsPriceSelector">
              <option data-value="70 €">día</option><option selected data-value="490 €">sem</option></select>'''

    async with SessionLocal() as session:
        with pytest.raises(ValueError, match="Holiday import scopes are disabled"):
            await provision_scopes(session, [ScopeDefinition("Pisos", "province:Madrid:holiday", (root,))])
        with pytest.raises(ValueError, match="Holiday import scopes are disabled"):
            await run_source(session, Source(), str(uuid4()), max_details=1)
        assert await session.scalar(select(Listing)) is None
        assert await session.scalar(select(ExternalListingSource)) is None


async def test_scope_checkpoint_drains_detail_tail_then_next_page_and_never_archives_unseen(monkeypatch):
    monkeypatch.setattr(external_import.get_settings(), "external_import_download_images", False)
    root = "https://www.pisos.com/alquiler/pisos-madrid/"
    pages, details = [], []

    class Source(PisosSource):
        scope_key = "province:Madrid"
        discovery_urls = (root,)
        max_discovery_pages = 1

        async def request(self, url):
            pages.append(url)
            assert not session.in_transaction()
            ids = (100101, 100102, 100103) if url == root else (100201,)
            links = ''.join(f'<a href="/alquilar/piso-madrid-{value}/">detail</a>' for value in ids)
            return links + f'<a href="{root}2/">next</a>'

        async def fetch_listing(self, url):
            details.append(url)
            assert not session.in_transaction()
            return '''<script type="application/ld+json">{"@type":"Apartment","propertyType":"apartment",
              "numberOfBedrooms":1,"name":"Piso en alquiler","description":"Oferta disponible",
              "address":{"addressLocality":"Madrid","addressRegion":"Madrid","addressCountry":"ES"},
              "geo":{"latitude":40.4,"longitude":-3.7}}</script><p>900 €/mes</p>'''

    async with SessionLocal() as session:
        await provision_scopes(session, [ScopeDefinition("Pisos", "province:Madrid", (root,))])
        assert await upsert(session, item(external_id="unseen-in-window"), scope_key="province:Madrid") == "imported"
        for _ in range(4):
            counters = await run_source(session, Source(), str(uuid4()), max_details=1)
            assert counters.result == "partial"
            assert counters["archived"] == 0
        row = await session.scalar(select(ExternalImportScope))
        assert row.discovery_checkpoint is None
        unseen = await session.scalar(select(ExternalListingSource).where(
            ExternalListingSource.external_id == "unseen-in-window"))
        assert unseen.current_status == "active" and unseen.consecutive_missing_runs == 0
        assert len(details) == len(set(details)) == 4
        assert pages == [root, root + '2/']


async def test_normalized_url_changed_id_retains_source_and_canonical(monkeypatch):
    monkeypatch.setattr(external_import.get_settings(), "external_import_download_images", False)
    async with SessionLocal() as session:
        original = item(source_url=item().source_url + "?from=list#gallery")
        assert await upsert(session, original, scope_key="province:Madrid") == "imported"
        source = await session.scalar(select(ExternalListingSource))
        listing_id, source_id = source.canonical_listing_id, source.id
        changed = item(external_id="new-property-id", source_url=item().source_url.rstrip("/"))
        await upsert(session, changed, scope_key="province:Madrid")
        assert await session.scalar(select(func.count(Listing.id))) == 1
        assert await session.scalar(select(func.count(ExternalListingSource.id))) == 1
        source = await session.get(ExternalListingSource, source_id)
        assert source.external_id == original.external_id and source.canonical_listing_id == listing_id
        assert await upsert(session, changed, scope_key="province:Madrid") == "unchanged"


@pytest.mark.parametrize(
    ("room_type", "count", "mode", "cadence"),
    [
        ("Estudio", 0, "long", "mes"),
        ("Apartamento de 1 dormitorio", 1, "long", "mes"),

    ],
)
async def test_whole_units_reach_run_source_and_canonical_prices(monkeypatch, room_type, count, mode, cadence):
    monkeypatch.setattr(external_import.get_settings(), "external_import_download_images", False)

    class Source(PisosSource):
        scope_key = "province:Madrid"

        async def discover_listing_urls(self):
            return DiscoveryResult(urls={item().source_url}, complete=True, visited_pages=1, reached_last_page=True)

        async def fetch_listing(self, url):
            kind = "studio" if count == 0 else "apartment"
            return f'''<script type="application/ld+json">{{"@type":"Apartment","propertyType":"{kind}",
              "numberOfBedrooms":{count},"name":"{room_type} en alquiler","description":"Oferta disponible",
              "address":{{"addressLocality":"Madrid","addressRegion":"Madrid","addressCountry":"ES"}},
              "geo":{{"latitude":40.4,"longitude":-3.7}}}}</script><p>90 €/{cadence}</p>'''

    async with SessionLocal() as session:
        counters = await run_source(session, Source(), str(uuid4()))
        assert counters.result == "partial"
        assert counters["incomplete_galleries"] == 1
        assert counters["accepted_rentals"] == counters[f"accepted_{mode}"] == 1
        assert counters["accepted_rooms"] == 0
        listing = await session.scalar(select(Listing))
        assert listing.room_type == room_type and listing.bedroom_count == (count or None)
        assert listing.rental_mode == mode
        assert (listing.monthly_price, listing.nightly_price) == ((90, None) if mode == "long" else (None, 90))
        source = await session.scalar(select(ExternalListingSource))
        assert source.scope_key == "province:Madrid" and source.normalized_payload["country"] == "ES"


@pytest.mark.parametrize("incomplete_root", [False, True])
async def test_bootstrap_detail_budget_remains_partial_and_does_not_archive_missing_source(monkeypatch, incomplete_root):
    monkeypatch.setattr(external_import.get_settings(), "external_import_download_images", False)

    class Source(PisosSource):
        scope_key = "province:Madrid"
        discovery_urls = ("https://www.pisos.com/alquiler/pisos-madrid/", "https://www.pisos.com/alquiler/pisos-madrid/2/")

        async def request(self, url):
            links = [item().source_url, "https://www.pisos.com/alquilar/piso-madrid-999999/"]
            if url == self.discovery_urls[1]:
                links = links[:1]
            return "2 resultados" + "".join(f'<a href="{link}">offer</a>' for link in links)

        async def discover_listing_urls(self):
            if incomplete_root:
                return await super().discover_listing_urls()
            return DiscoveryResult(
                urls={item().source_url, "https://www.pisos.com/alquilar/piso-madrid-999999/"},
                complete=True,
                visited_pages=1,
                reached_last_page=True,
            )

        async def fetch_listing(self, url):
            return "<h1>unused</h1>"

        def parse_listing(self, document, url):
            return {
                "title": "Estudio en alquiler",
                "property_type": "studio",
                "bedroom_count": 0,
                "city": "Madrid",
                "province": "Madrid",
                "country": "ES",
                "price_text": "700 €/mes",
                "url": url,
            }

    async with SessionLocal() as session:
        existing = item(external_id="outside-budget", source_url="https://www.pisos.com/alquilar/piso-madrid-000000/")
        await upsert(session, existing, scope_key="province:Madrid")
        async def forbidden_archive(*args):
            pytest.fail("Partial root/detail discovery must never call archive_missing")
        monkeypatch.setattr(external_import, "archive_missing", forbidden_archive)
        counters = await run_source(session, Source(), str(uuid4()), max_details=None if incomplete_root else 1)
        assert counters.result == "partial"
        record = await session.scalar(
            select(ExternalListingSource).where(ExternalListingSource.external_id == "outside-budget")
        )
        assert record.current_status == "active" and record.consecutive_missing_runs == 0
        run = await session.scalar(select(ExternalImportRun))
        assert not run.discovery_complete
        if not incomplete_root:
            assert "bootstrap_detail_budget" in run.discovery_failed_pages


async def test_identical_gallery_deduplicates_same_mode_but_preserves_holiday_offer(monkeypatch):
    monkeypatch.setattr(external_import.get_settings(), "external_import_download_images", False)
    fingerprints = [
        ImageFingerprint(
            asset_id=None, checksum=f"spain-photo-{i}", perceptual_hash=f"{i + 1:016x}", width=16, height=16
        )
        for i in range(4)
    ]

    async def public_fingerprints(urls):
        return fingerprints

    monkeypatch.setattr(external_import, "public_image_fingerprints", public_fingerprints)
    async with SessionLocal() as session:
        first = item(photos=[f"https://images.example.test/{i}.webp" for i in range(4)])
        await upsert(session, first, scope_key="province:Madrid")
        canonical = await session.scalar(select(Listing))
        for i, fingerprint in enumerate(fingerprints):
            asset = MediaAsset(
                owner_id=canonical.owner_user_id,
                storage_key=f"spain-{uuid4()}.webp",
                mime_type="image/webp",
                size_bytes=1,
                width=16,
                height=16,
                checksum=fingerprint.checksum,
                perceptual_hash=fingerprint.perceptual_hash,
                kind="listing_image",
            )
            session.add(asset)
            await session.flush()
            session.add(ListingImage(listing_id=canonical.id, media_asset_id=asset.id, sort_order=i))
        await session.commit()
        second = replace(
            first,
            source_name="Fotocasa",
            external_id="second-provider",
            source_url="https://www.fotocasa.es/es/alquiler/vivienda/madrid/123456/d",
        )
        await upsert(session, second, scope_key="province:Madrid")
        assert await session.scalar(select(func.count(Listing.id))) == 1
        holiday = replace(
            first,
            external_id="holiday-offer",
            source_url="https://www.pisos.com/alquilar/piso-madrid-654321/",
            rental_mode="holiday",
            price_period="night",
            price_amount=85,
            source_price_text="85 €/noche",
        )
        assert await upsert(session, holiday, scope_key="province:Madrid") == "policy_rejected"
        assert await session.scalar(select(func.count(Listing.id))) == 1
        assert await session.scalar(select(func.count(ExternalListingSource.id))) == 2


@pytest.mark.parametrize("ceiling", [False, True])
async def test_bootstrap_checkpoint_resumes_scope_rounds_and_respects_small_budgets(monkeypatch, tmp_path, ceiling):
    from app.commands import bootstrap_external_spain as command
    from app.services.external_import import SourceRunCounters

    definitions = [
        ScopeDefinition("Pisos", "province:" + province, (f"https://www.pisos.com/alquiler/pisos-{province.lower()}/",))
        for province in ("Madrid", "Barcelona")
    ]
    async with SessionLocal() as session:
        await provision_scopes(session, definitions, enable=True)
    monkeypatch.setattr(
        command,
        "get_settings",
        lambda: SimpleNamespace(external_import_enabled=True, external_import_nationwide_enabled=True),
    )
    monkeypatch.setattr(command, "configured_sources", lambda: [PisosSource()])

    @asynccontextmanager
    async def lease(**kwargs):
        yield

    monkeypatch.setattr(command, "import_lease", lease)
    attempts = []
    current_total = 2999 if ceiling else 2600

    async def bounded_import(session, source, run_id, *, max_details):
        nonlocal current_total
        attempts.append((source.max_discovery_pages, max_details))
        if ceiling:
            assert max_details == 1
            current_total += max_details
        counters = SourceRunCounters({"accepted_rentals": 1})
        counters.result = "partial"
        return counters

    monkeypatch.setattr(command, "run_source", bounded_import)

    async def long_only_totals(session):
        return {"total": current_total, "by_mode": {"long": current_total, "holiday": 0}}

    monkeypatch.setattr(command, "canonical_totals", long_only_totals)
    args = Namespace(
        apply=True,
        manifest=None,
        worker_paused=False,
        max_pages=1,
        max_details=2,
        max_scopes=1,
        target_total=2500,
        target_holiday_min=500,
        max_total=3000,
        checkpoint=tmp_path / "checkpoint.json",
        restart=False,
    )
    first = await command.execute(args)
    stop = "max_total_reached_holiday_unmet" if ceiling else "scope_budget_reached"
    assert first["stop"] == stop and len(attempts) == 1
    assert first["objective"]["total_target_satisfied"] and not first["objective"]["holiday_min_satisfied"]
    args.max_scopes = 3
    resumed = await command.execute(args)
    assert resumed["stop"] == (stop if ceiling else "reviewed_scope_rounds_exhausted") and not resumed["objective"]["satisfied"]
    assert attempts == ([(1, 1)] if ceiling else [(1, 2), (1, 2)])
    assert (await command.execute(args))["results"] == []
