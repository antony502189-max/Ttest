"""Exercise real importer control flow with in-memory session boundaries.

These tests deliberately perform no network, object storage or database I/O.
PostgreSQL persistence remains covered by tests/integration, separately.
"""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.external_sources import NormalizedListing
from app.models import ExternalListingSource, Listing
from app.models.room_details import ListingRoomDetails
from app.services import external_import


def item(**changes):
    return replace(
        NormalizedListing(
            source_name="Flatio",
            external_id="123",
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


class MemorySession:
    def __init__(self):
        self.listings = {}
        self.sources = []
        self.details = {}
        self.commits = 0
        self.catalog_touches = 0

    def add(self, row):
        if isinstance(row, Listing):
            row.id = row.id or uuid4()
            self.listings[row.id] = row
        elif isinstance(row, ExternalListingSource):
            row.id = row.id or uuid4()
            self.sources.append(row)
        elif isinstance(row, ListingRoomDetails):
            self.details[row.listing_id] = row
        else:
            raise TypeError(type(row))

    async def flush(self):
        pass

    async def commit(self):
        self.commits += 1

    def in_transaction(self):
        return False

    async def scalar(self, query):
        params = query.compile().params
        name = params["source_name_1"]
        return next(
            (
                row
                for row in self.sources
                if row.source_name == name
                and (row.external_id == params.get("external_id_1") or row.source_url == params.get("rtrim_1"))
            ),
            None,
        )

    async def scalars(self, query):
        params = query.compile().params
        return SimpleNamespace(
            all=lambda: [
                row
                for row in self.sources
                if row.canonical_listing_id == params["canonical_listing_id_1"] and row.current_status == "active"
            ]
        )

    async def get(self, model, key):
        if model is Listing:
            return self.listings.get(key)
        if model is ListingRoomDetails:
            return self.details.get(key)
        raise AssertionError(model)


@pytest.fixture
def importer(monkeypatch):
    session = MemorySession()
    monkeypatch.setattr(
        external_import,
        "get_settings",
        lambda: SimpleNamespace(
            external_import_download_images=False,
            external_import_preserve_existing_data=False,
        ),
    )
    monkeypatch.setattr(external_import, "public_image_fingerprints", AsyncMock(return_value=[]))
    monkeypatch.setattr(external_import, "acquire_duplicate_guard", AsyncMock())
    monkeypatch.setattr(
        external_import, "canonical_for", AsyncMock(side_effect=lambda *_: next(iter(session.listings.values()), None))
    )
    monkeypatch.setattr(external_import, "system_user", AsyncMock(return_value=SimpleNamespace(id=uuid4())))
    monkeypatch.setattr(external_import, "import_images", AsyncMock())
    monkeypatch.setattr(external_import, "notify_saved_search_matches", AsyncMock())
    monkeypatch.setattr(external_import, "notify_favorited_listing_unavailable", AsyncMock())

    async def touch(session):
        session.catalog_touches += 1

    monkeypatch.setattr(external_import, "touch_catalog", touch)
    return session


@pytest.mark.parametrize(
    "field,first,second",
    [
        ("pets_allowed", True, False),
        ("children_allowed", True, False),
        ("smoking_allowed", False, True),
        ("furnished", False, True),
        ("room_capacity", 1, 4),
        ("pets_allowed", False, None),
    ],
)
async def test_optional_only_updates_reach_canonical_and_repeat_is_noop(importer, field, first, second):
    original = item(**{field: first})
    assert await external_import.upsert(importer, original) == "imported"
    revised = replace(original, **{field: second})
    assert await external_import.upsert(importer, revised) == "updated"
    listing = next(iter(importer.listings.values()))
    actual = importer.details[listing.id].room_capacity_v2 if field == "room_capacity" else getattr(listing, field)
    assert actual == second
    assert importer.sources[0].normalized_payload[field] == second
    touches = importer.catalog_touches
    assert await external_import.upsert(importer, revised) == "unchanged"
    assert importer.catalog_touches == touches
    assert len(importer.listings) == len(importer.sources) == 1


@pytest.mark.parametrize("capacity", [1, 2, 3, 4, 7, 10])
async def test_occupancy_survives_creation_sync_and_primary_promotion(importer, capacity):
    original = item(room_capacity=capacity)
    assert await external_import.upsert(importer, original) == "imported"
    listing = next(iter(importer.listings.values()))
    assert listing.room_capacity == min(2, capacity)
    assert importer.details[listing.id].room_capacity_v2 == capacity
    revised = replace(original, room_capacity=5 if capacity != 5 else 6)
    assert await external_import.upsert(importer, revised) == "updated"
    other = replace(original, source_name="Fotocasa", external_id="456", source_url="https://www.fotocasa.es/456")
    assert await external_import.upsert(importer, other, force_primary=True) == "updated"
    assert len(importer.listings) == 1 and len(importer.sources) == 2
    assert listing.primary_source == "Fotocasa"
    assert importer.details[listing.id].room_capacity_v2 == capacity
    assert await external_import.deactivate_source_record(importer, importer.sources[1], "removed") == 0
    assert listing.primary_source == "Flatio"
    assert importer.details[listing.id].room_capacity_v2 == revised.room_capacity


async def test_conflicts_remain_per_source_and_unknown_primary_does_not_invent_permission(importer):
    allowed = item(pets_allowed=True, room_capacity=4)
    denied = replace(
        allowed, source_name="Fotocasa", source_url="https://www.fotocasa.es/456", external_id="456", pets_allowed=False
    )
    unknown = replace(
        allowed,
        source_name="Habitaclia",
        source_url="https://www.habitaclia.com/i789.htm",
        external_id="789",
        pets_allowed=None,
        room_capacity=None,
    )
    for value in (allowed, denied, unknown):
        await external_import.upsert(importer, value, force_primary=True)
    listing = next(iter(importer.listings.values()))
    assert listing.pets_allowed is None and listing.room_capacity is None
    assert importer.details[listing.id].room_capacity_v2 is None
    assert [source.normalized_payload["pets_allowed"] for source in importer.sources] == [True, False, None]
    await external_import.deactivate_source_record(importer, importer.sources[2], "removed")
    assert listing.primary_source in {"Flatio", "Fotocasa"}
    assert listing.pets_allowed == (listing.primary_source == "Flatio")


async def test_restoration_keeps_identity_and_partial_gallery_keeps_existing_images(importer):
    original = item()
    await external_import.upsert(importer, original)
    listing = next(iter(importer.listings.values()))
    listing.external_image_urls = ["https://example.test/old.jpg"]
    partial = replace(
        original,
        photos=["https://example.test/partial.jpg"],
        raw_payload={"photos_complete": False},
        pets_allowed=False,
    )
    assert await external_import.upsert(importer, partial) == "updated"
    assert listing.external_image_urls == ["https://example.test/old.jpg"]
    external_import.import_images.assert_not_awaited()
    listing.status, listing.closed_reason = "closed", "removed"
    assert await external_import.upsert(importer, partial) == "restored"
    assert len(importer.listings) == 1 and listing.status == "published"


async def test_empty_description_and_unknown_values_are_explicitly_applied(importer):
    value = item(description="")
    await external_import.upsert(importer, value)
    listing = next(iter(importer.listings.values()))
    assert listing.description == ""
    for field in ("pets_allowed", "children_allowed", "smoking_allowed", "room_capacity", "furnished"):
        assert getattr(listing, field) is None


async def test_capacity_above_existing_contract_is_retained_in_source_snapshot(importer):
    # The existing owner/search capacity contract is 1..10. Do not silently
    # widen that API in an importer audit. Evidence input supports up to 99.
    await external_import.upsert(importer, item(room_capacity=11))
    listing = next(iter(importer.listings.values()))
    assert listing.room_capacity is None
    assert listing.id not in importer.details
    assert importer.sources[0].normalized_payload["room_capacity"] == 11


def test_legacy_defaults_cannot_prove_owner_intent():
    from app.schemas.listings import ListingWrite

    # Both the ORM and owner DTO carry defaults. A stored False/1/True cannot
    # recover model_fields_set or establish which form choice was explicit.
    assert Listing.__table__.c.pets_allowed.default.arg is False
    assert Listing.__table__.c.room_capacity.default.arg == 1
    assert Listing.__table__.c.furnished.default.arg is True
    assert ListingWrite.model_fields["petsAllowed"].default is False
    assert ListingWrite.model_fields["roomCapacity"].default == 1
