from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from time import perf_counter
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select, update

from app.db.session import SessionLocal, engine
from app.external_sources import NormalizedListing
from app.models import AuditLog, ExternalListingSource, Favorite, Listing, ListingImage, MediaAsset, Notification
from app.models.storage_deletion import StorageDeletionJob
from app.services import external_import, storage_deletions
from app.services.external_removal import new_report, purge_confirmed_removed_source, reconcile_source

pytestmark = pytest.mark.integration


def external_item(*, source, external_id, url, price=710):
    return NormalizedListing(
        source_name=source,
        external_id=external_id,
        source_url=url,
        title="Habitación exterior",
        description="Habitación individual en Adeje",
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
    )


class Probe:
    name = "Idealista"

    def __init__(self, session, state="active"):
        self.session, self.state = session, state
        self.calls = []
        self.running = self.maximum = 0

    async def check_listing_state(self, url):
        assert not self.session.in_transaction()
        self.calls.append(url)
        self.running += 1
        self.maximum = max(self.maximum, self.running)
        try:
            await asyncio.sleep(0.001)
            return self.state
        finally:
            self.running -= 1


async def seed(session):
    item = external_item(source="Idealista", external_id="one", url="https://example.test/one")
    await external_import.upsert(session, item)
    await session.commit()
    row = await session.scalar(select(ExternalListingSource))
    return row, await session.get(Listing, row.canonical_listing_id)


@pytest.mark.parametrize(
    "state", ["active", "removed", "expired", "not_found", "blocked", "temporary_error", "unknown"]
)
async def test_direct_state_contract_and_repeated_unknown(state):
    async with SessionLocal() as session:
        _row, listing = await seed(session)
        source_id, canonical_id = _row.id, listing.id
        await session.commit()
        report = new_report()
        await reconcile_source(session, Probe(session, state), report=report)
        confirmed = state in {"removed", "expired", "not_found"}
        assert report["checked"] == 1
        assert report["canonical_listings_purged"] == int(confirmed)
        # Fresh reads also prove physical deletion, rather than an identity-map transition.
        session.expunge_all()
        row = await session.get(ExternalListingSource, source_id)
        listing = await session.get(Listing, canonical_id)
        if confirmed:
            assert row is None and listing is None
        else:
            assert row.current_status == "active" and listing.status == "published"
            assert row.last_state_check_result == state
            if state == "unknown":
                await session.commit()
                await reconcile_source(session, Probe(session, state))
                await session.refresh(row)
                assert row.consecutive_unknown_state_runs == 2 and listing.status == "published"


@pytest.mark.parametrize("remove_primary", [True, False])
async def test_alternative_source_survives_with_valid_primary_without_import_io(monkeypatch, remove_primary):
    async with SessionLocal() as session:
        _row, listing = await seed(session)
        alternative = external_item(source="Fotocasa", external_id="two", url="https://example.test/two", price=990)
        session.add(
            ExternalListingSource(
                source_name="Fotocasa",
                external_id="two",
                source_url=alternative.source_url,
                canonical_listing_id=listing.id,
                fingerprint="b" * 64,
                normalized_payload=external_import.normalized_snapshot(alternative),
            )
        )
        await session.commit()

        def forbidden(*args, **kwargs):
            raise AssertionError("Removal cannot invoke full import or media I/O")

        monkeypatch.setattr(external_import, "upsert", forbidden)
        monkeypatch.setattr(external_import, "public_image_fingerprints", forbidden)
        probe = Probe(session, "removed")
        probe.name = "Idealista" if remove_primary else "Fotocasa"
        report = new_report()
        await reconcile_source(session, probe, report=report)
        await session.refresh(listing)
        assert listing.status == "published"
        assert listing.primary_source == ("Fotocasa" if remove_primary else "Idealista")
        assert listing.monthly_price == (990 if remove_primary else 710)
        assert report["canonical_sources_promoted"] == int(remove_primary)
        assert report["canonical_listings_purged"] == 0
        assert await session.scalar(select(func.count()).select_from(ExternalListingSource)) == 1


async def test_native_relation_fails_closed_and_snapshot_race_is_not_applied():
    async with SessionLocal() as session:
        _row, listing = await seed(session)
        source_id, canonical_id = _row.id, listing.id
        row = _row
        listing.is_external = False
        await session.commit()
        report = new_report()
        await reconcile_source(session, Probe(session, "removed"), report=report)
        assert report["failed"] == 1 and report["source_rows_purged"] == 0
        assert await session.get(Listing, canonical_id) is not None
        with pytest.raises(ValueError, match="native"):
            await purge_confirmed_removed_source(session, source_id, "removed")
        await session.rollback()
        with pytest.raises(ValueError, match="authoritative"):
            await purge_confirmed_removed_source(session, uuid4(), "unknown")
        # A refreshed source after the snapshot must not be removed by stale probe evidence.
        row = await session.scalar(select(ExternalListingSource))
        listing = await session.get(Listing, row.canonical_listing_id)
        listing.is_external = True
        snapshot = datetime.now(UTC)
        row.last_seen_at = snapshot + timedelta(seconds=1)
        await session.commit()
        report = new_report()
        await reconcile_source(session, Probe(session, "removed"), started_at=snapshot, report=report)
        assert report["checked"] == 1 and report["source_rows_purged"] == 0
        assert await session.get(ExternalListingSource, source_id) is not None


@pytest.mark.parametrize("state", ["active", "blocked", "temporary_error"])
async def test_150_record_keyset_sweep_bounded_http_and_provider_circuit(state, record_property):
    async with SessionLocal() as session:
        _row, listing = await seed(session)
        for index in range(1, 150):
            session.add(
                ExternalListingSource(
                    source_name="Idealista",
                    external_id=str(index),
                    source_url=f"https://example.test/load/{index}",
                    canonical_listing_id=listing.id,
                    fingerprint="a" * 64,
                    scope_key="province:Madrid" if index % 2 else "province:Málaga",
                )
            )
        # Exclude a record created after the finite sweep snapshot.
        snapshot = datetime.now(UTC) + timedelta(seconds=1)
        session.add(
            ExternalListingSource(
                source_name="Idealista",
                external_id="future",
                source_url="https://example.test/future",
                canonical_listing_id=listing.id,
                fingerprint="c" * 64,
                first_seen_at=snapshot + timedelta(seconds=1),
            )
        )
        await session.commit()
        batch_sql = []

        def capture(_connection, _cursor, statement, _parameters, _context, _many):
            if statement.startswith("SELECT external_listing_sources.id, external_listing_sources.source_url"):
                batch_sql.append(statement)

        event.listen(engine.sync_engine, "before_cursor_execute", capture)
        report, probe = new_report(), Probe(session, state)
        started = perf_counter()
        try:
            await reconcile_source(session, probe, started_at=snapshot, report=report)
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", capture)
        record_property("sweep_duration_seconds", round(perf_counter() - started, 3))
        record_property("checked", report["checked"])
        record_property("batches", report["batches"])
        record_property("maximum_http", probe.maximum)
        assert report["candidate_records"] == 150 and probe.maximum <= 3
        assert len(set(probe.calls)) == len(probe.calls)
        assert all("OFFSET" not in sql for sql in batch_sql)
        if state == "active":
            assert report["checked"] == 150 and report["batches"] == 2 and len(batch_sql) == 3
            assert "external_listing_sources.id >" in batch_sql[1]
        else:
            assert 5 <= report["checked"] <= 7
            assert report["checked"] + report["deferred_by_circuit_breaker"] == 150
            assert report["result"] == "partial"
            assert await session.scalar(select(func.count()).select_from(ExternalListingSource)) == 151
            await session.commit()
            reset = new_report()
            await reconcile_source(session, Probe(session), started_at=snapshot, report=reset)
            assert reset["checked"] == 150  # Circuit is local to this provider/sweep.


async def test_last_source_purge_cascades_favorites_retains_audit_and_queues_only_orphans(monkeypatch):
    async with SessionLocal() as session:
        _row, listing = await seed(session)
        canonical_id = listing.id
        native = Listing(
            owner_user_id=listing.owner_user_id,
            title="Native",
            city="Adeje",
            area="Adeje",
            approximate_address="Adeje",
            rental_mode="long",
            monthly_price=700,
            is_external=False,
            status="published",
        )
        session.add(native)
        assets = [
            MediaAsset(
                owner_id=listing.owner_user_id,
                storage_key=f"test/removal/{uuid4()}",
                mime_type="video/mp4" if index == 2 else "image/webp",
                size_bytes=16,
                width=16,
                height=16,
                checksum="a" * 64,
                kind="listing_image",
            )
            for index in range(3)
        ]
        session.add_all(assets)
        await session.flush()
        session.add_all(
            [
                ListingImage(listing_id=listing.id, media_asset_id=assets[0].id, sort_order=0),
                ListingImage(listing_id=listing.id, media_asset_id=assets[1].id, sort_order=1),
                ListingImage(listing_id=native.id, media_asset_id=assets[1].id, sort_order=0),
                Favorite(user_id=listing.owner_user_id, listing_id=listing.id),
                AuditLog(action="review", target_type="listing", target_id=listing.id),
            ]
        )
        listing.video_asset_id = assets[2].id
        await session.commit()

        def forbidden():
            raise AssertionError("No synchronous storage access in purge")

        monkeypatch.setattr(storage_deletions, "get_storage", forbidden)
        report = new_report()
        await reconcile_source(session, Probe(session, "not_found"), report=report)
        assert report["media_assets_orphaned"] == report["storage_deletions_enqueued"] == 2
        session.expunge_all()
        assert await session.get(Listing, canonical_id) is None
        assert await session.get(Listing, native.id) is not None
        assert await session.scalar(select(func.count()).select_from(Favorite)) == 0
        assert await session.scalar(select(func.count()).select_from(AuditLog)) == 1
        assert await session.scalar(select(func.count()).select_from(ListingImage)) == 1
        assert set((await session.scalars(select(StorageDeletionJob.storage_key))).all()) == {
            assets[0].storage_key,
            assets[2].storage_key,
        }
        notification = await session.scalar(select(Notification).where(Notification.type == "favorite_unavailable"))
        assert notification is not None and notification.entity_listing_id is None
        assert (await session.get(MediaAsset, assets[1].id)).deleted_at is None
        assert (await session.get(MediaAsset, assets[0].id)).deleted_at is not None


async def test_shared_http_limit_and_isolated_adapter_failure():
    async with SessionLocal() as session:
        _row, listing = await seed(session)
        for name in ("Idealista", "Fotocasa"):
            for index in range(6):
                session.add(
                    ExternalListingSource(
                        source_name=name,
                        external_id=f"{name}-{index}",
                        source_url=f"https://example.test/{name}/{index}",
                        canonical_listing_id=listing.id,
                        fingerprint="a" * 64,
                    )
                )
        await session.commit()
    running = maximum = 0
    ready = asyncio.Event()

    class Adapter(Probe):
        async def check_listing_state(self, url):
            nonlocal running, maximum
            assert not self.session.in_transaction()
            running += 1
            maximum = max(maximum, running)
            try:
                if running == 4:
                    ready.set()
                await asyncio.wait_for(ready.wait(), timeout=1)
                await asyncio.sleep(0.001)
                if url.endswith("Idealista/0"):
                    raise RuntimeError("isolated adapter failure")
                return "active"
            finally:
                running -= 1

    async with SessionLocal() as first, SessionLocal() as second:
        limit, reports = asyncio.Semaphore(4), [new_report(), new_report()]
        adapters = [Adapter(first), Adapter(second)]
        adapters[1].name = "Fotocasa"
        await asyncio.gather(
            *(
                reconcile_source(session, adapter, global_limit=limit, report=report)
                for session, adapter, report in zip((first, second), adapters, reports)
            )
        )
        assert maximum == 4
        assert reports[0]["checked"] == 7 and reports[0]["failed"] == 1
        assert reports[1]["checked"] == 6 and reports[1]["result"] == "success"


@pytest.mark.parametrize("changed_field", ["native", "url"])
async def test_probe_reloads_cached_rows_before_mutation(changed_field):
    async with SessionLocal() as session:
        row, listing = await seed(session)
        source_id, canonical_id = row.id, listing.id
        await session.commit()

        class ConcurrentChange(Probe):
            async def check_listing_state(self, url):
                assert not session.in_transaction()
                async with SessionLocal() as writer:
                    if changed_field == "native":
                        await writer.execute(
                            update(Listing).where(Listing.id == canonical_id).values(is_external=False)
                        )
                    else:
                        await writer.execute(
                            update(ExternalListingSource)
                            .where(ExternalListingSource.id == source_id)
                            .values(source_url="https://example.test/newer-url")
                        )
                    await writer.commit()
                return "removed"

        report = new_report()
        await reconcile_source(session, ConcurrentChange(session), report=report)
        assert report["source_rows_purged"] == report["canonical_listings_purged"] == 0
        assert report["failed"] == (1 if changed_field == "native" else 0)
        session.expunge_all()
        assert await session.get(ExternalListingSource, source_id) is not None
        assert await session.get(Listing, canonical_id) is not None
