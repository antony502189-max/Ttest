"""PostgreSQL persistence regressions; only run against an isolated test DB."""

from dataclasses import replace

import pytest
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.external_sources import NormalizedListing
from app.models import ExternalListingSource, Listing, ListingRoomDetails
from app.services import external_import

pytestmark = pytest.mark.integration


def item(**changes):
    return replace(
        NormalizedListing(
            source_name="Flatio",
            external_id="ai-fixture",
            source_url="https://www.flatio.com/rent/room/123",
            title="Habitación en Adeje",
            description="Habitación luminosa.",
            city="Adeje",
            area="Adeje",
            rental_mode="long",
            source_price_text="600 €/mes",
            price_amount=600,
            price_currency="EUR",
            price_period="month",
            price_is_from=False,
        ),
        **changes,
    )


@pytest.mark.parametrize("capacity", [1, 2, 3, 4, 7, 10])
async def test_real_import_optional_updates_unknowns_and_capacity(monkeypatch, capacity):
    async def no_images(_urls):
        return []

    monkeypatch.setattr(external_import, "public_image_fingerprints", no_images)
    original = item(room_capacity=capacity, pets_allowed=True, children_allowed=True, furnished=True)
    async with SessionLocal() as session:
        assert await external_import.upsert(session, original) == "imported"
        listing = await session.scalar(select(Listing).where(Listing.is_external.is_(True)))
        listing_id = listing.id
    async with SessionLocal() as session:
        listing = await session.get(Listing, listing_id)
        details = await session.get(ListingRoomDetails, listing_id)
        assert listing.room_capacity == min(capacity, 2)
        assert details.room_capacity_v2 == capacity
        changed = replace(original, room_capacity=4, pets_allowed=False, children_allowed=None, furnished=None)
        assert await external_import.upsert(session, changed) == "updated"
    async with SessionLocal() as session:
        listing = await session.get(Listing, listing_id)
        details = await session.get(ListingRoomDetails, listing_id)
        assert listing.pets_allowed is False
        assert listing.children_allowed is None and listing.furnished is None
        assert details.room_capacity_v2 == 4
        assert await external_import.upsert(session, changed) == "unchanged"
        assert await session.scalar(select(func.count()).select_from(Listing)) == 1
        assert await session.scalar(select(func.count()).select_from(ExternalListingSource)) == 1


async def test_real_initial_unknowns_are_not_replaced_by_orm_defaults(monkeypatch):
    async def no_images(_urls):
        return []

    monkeypatch.setattr(external_import, "public_image_fingerprints", no_images)
    async with SessionLocal() as session:
        assert await external_import.upsert(session, item()) == "imported"
    async with SessionLocal() as session:
        listing = await session.scalar(select(Listing).where(Listing.is_external.is_(True)))
        for field in ("pets_allowed", "children_allowed", "smoking_allowed", "room_capacity", "furnished"):
            assert getattr(listing, field) is None


async def test_database_audit_is_repeatable_and_leaves_source_rows_unchanged(monkeypatch):
    import os

    from app.commands.audit_ai_listing_data import _database_report

    async def no_images(_urls):
        return []

    monkeypatch.setattr(external_import, "public_image_fingerprints", no_images)
    async with SessionLocal() as session:
        await external_import.upsert(session, item(description="No se admiten mascotas.", pets_allowed=False))
        before = (
            await session.execute(
                select(
                    ExternalListingSource.id,
                    ExternalListingSource.normalized_payload,
                    ExternalListingSource.fingerprint,
                    ExternalListingSource.current_status,
                )
            )
        ).all()
    first = await _database_report(os.environ["TEST_DATABASE_URL"], False)
    second = await _database_report(os.environ["TEST_DATABASE_URL"], False)
    assert first == second and first["records"] == 1
    assert first["sources"]["Flatio"]["policies"]["pets_allowed"]["explicit_pct"] == 100
    async with SessionLocal() as session:
        after = (
            await session.execute(
                select(
                    ExternalListingSource.id,
                    ExternalListingSource.normalized_payload,
                    ExternalListingSource.fingerprint,
                    ExternalListingSource.current_status,
                )
            )
        ).all()
        assert before == after
