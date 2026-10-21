from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from test_listing_photo_contract import listing_payload

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.external_sources import NormalizedListing
from app.main import app
from app.models import ExternalListingSource, Listing, MailOutbox, Notification, User
from app.models.moderation import ListingPromotion
from app.services import address_geography
from app.services.external_import import upsert

pytestmark = pytest.mark.integration

# Fixed provider evidence, independent of the submitted client payload.
ADDRESSES = [
    {"id": "madrid", "type": "portal", "countryCode": "011", "muniCode": "28079", "provinceCode": "28", "postalCode": "28013",
         "muni": "Madrid", "poblacion": "Madrid", "address": "CALLE MAYOR 1, Madrid", "lat": 40.4168, "lng": -3.7038},
    {"id": "getafe", "type": "portal", "countryCode": "011", "muniCode": "28065", "provinceCode": "28", "postalCode": "28901",
         "muni": "Getafe", "poblacion": "Getafe", "address": "CALLE MAYOR 1, Getafe", "lat": 40.3083, "lng": -3.7327},
    {"id": "barcelona", "type": "portal", "countryCode": "011", "muniCode": "08019", "provinceCode": "08", "postalCode": "08001",
         "muni": "Barcelona", "poblacion": "Barcelona", "address": "CALLE MAYOR 1, Barcelona", "lat": 41.38, "lng": 2.17},
]


@pytest.fixture
def authoritative_addresses(monkeypatch):
    monkeypatch.setattr(address_geography, "address_candidates", AsyncMock(return_value=ADDRESSES))


def payload_for(row, assets):
    return {**listing_payload("Verified geography room", assets), "street": "Calle Mayor 1", "postcode": row["postalCode"],
            "city": row["muni"], "latitude": row["lat"], "longitude": row["lng"],
            "exactLatitude": row["lat"], "exactLongitude": row["lng"]}


async def direct_client(headers):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver",
                       headers={"Origin": "http://testserver", **headers})


async def test_authenticated_create_patch_owner_address_and_private_contract(client, register_user, authoritative_addresses):
    token, user = await register_user(client, email="verified-address@example.com", role="host")
    headers = {"Authorization": "Bearer " + token}
    assets = await client.seed_listing_assets(user["id"], 5)
    data = payload_for(ADDRESSES[0], assets)
    async with await direct_client(headers) as direct:
        for change in [{"postcode": "08001"}, {"postcode": ""}, {"postcode": "garbage"},
                       {"exactLatitude": 41.38, "exactLongitude": 2.17}]:
            rejected = await direct.post("/api/v1/listings", json={**data, **change})
            assert rejected.status_code == 422, rejected.text
        created = await direct.post("/api/v1/listings", json=data)
        assert created.status_code == 201, created.text
        listing_id = created.json()["id"]
        assert created.json()["provinceCode"] == "28"
        for change in [{"postcode": "08001"}, {"latitude": 41.38, "longitude": 2.17},
                       {"exactLatitude": 41.38, "exactLongitude": 2.17}]:
            rejected = await direct.patch("/api/v1/listings/" + listing_id, json=change)
            assert rejected.status_code == 422, rejected.text
        for row, expected, excluded in [(ADDRESSES[2], "08", "28"), (ADDRESSES[0], "28", "08")]:
            address = payload_for(row, assets)
            move = await direct.patch("/api/v1/listings/" + listing_id, json={key: address[key] for key in (
                "street", "postcode", "city", "latitude", "longitude", "exactLatitude", "exactLongitude",
            )})
            assert move.status_code == 200 and move.json()["provinceCode"] == expected, move.text
            included = await direct.post("/api/v1/listings/search/cards", json={"provinceCode": expected})
            absent = await direct.post("/api/v1/listings/search/cards", json={"provinceCode": excluded})
            assert listing_id in str(included.json()) and listing_id not in str(absent.json())
        async with SessionLocal() as db:
            owner = await db.get(User, UUID(user["id"]))
            owner.address_verified_at = None
            owner.municipality_code = None
            await db.commit()
        missing = await direct.get(f"/api/v1/payments/listings/{listing_id}/top/availability")
        assert missing.status_code == 409
        saved = await direct.put("/api/v1/users/me/address", json={"street": "Calle Mayor 1", "postcode": "28901", "city": "Getafe"})
        assert saved.status_code == 200, saved.text
        available = await direct.get(f"/api/v1/payments/listings/{listing_id}/top/availability")
        assert available.json()["municipalityCode"] == "28065"  # owner Getafe, property Madrid
        profile = await direct.get("/api/v1/users/me")
        assert "verified_address" not in profile.json() and "municipalityCode" not in profile.json()
    assert (await client.get("/api/v1/users/me/address")).status_code == 401


async def test_import_without_postcode_participates_in_all_province_surfaces(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "external_import_download_images", False)
    item = NormalizedListing(source_name="Pisos", external_id=uuid4().hex,
        source_url="https://www.pisos.com/alquilar/remediation-test/", title="Madrid imported room",
        description="Isolated fixture", city="Madrid", area="Centro", rental_mode="long",
        source_price_text="500 €/mes", price_amount=500, price_currency="EUR", price_period="month", price_is_from=False,
        province="Madrid", country="ES", latitude=40.4168, longitude=-3.7038)
    async with SessionLocal() as db:
        assert await upsert(db, item, scope_key="province:Madrid") == "imported"
        source = await db.scalar(select(ExternalListingSource).where(ExternalListingSource.external_id == item.external_id))
        row = await db.get(Listing, source.canonical_listing_id)
        listing_id = str(row.id)
        assert row.postcode == "" and row.province_code == "28"
    for path in ["/search", "/search/cards", "/map"]:
        result = await client.post("/api/v1/listings" + path, json={"provinceCode": "28", **({"north": 41.2, "south": 39.8, "east": -3.0, "west": -4.6, "zoom": 16} if path == "/map" else {})})
        assert result.status_code == 200, result.text
        assert listing_id in str(result.json())
        other = await client.post("/api/v1/listings" + path, json={"provinceCode": "08", **({"north": 41.2, "south": 39.8, "east": -3.0, "west": -4.6, "zoom": 16} if path == "/map" else {})})
        assert listing_id not in str(other.json())
    counts = await client.post("/api/v1/listings/provinces/counts", json={})
    assert next(row for row in counts.json()["items"] if row["id"] == "28")["count"] == 1
    locations = await client.post("/api/v1/listings/locations/counts", json={"rentalMode": "long"})
    assert locations.status_code == 200, locations.text
    assert locations.json()["municipalities"] == [{"id": "28079", "count": 1}]
    holiday_locations = await client.post("/api/v1/listings/locations/counts", json={"rentalMode": "holiday"})
    assert holiday_locations.json()["municipalities"] == []
    async with SessionLocal() as db:
        await upsert(db, item, scope_key="province:Madrid")
        assert (await db.get(Listing, UUID(listing_id))).province_code == "28"
        row = await db.get(Listing, UUID(listing_id))
        row.province_code = None
        await db.commit()
        from app.commands.backfill_geography import backfill
        plan = await backfill(db)
        assert plan["provinces"] == [{"listingId": listing_id, "provinceCode": "28"}]
        assert (await db.get(Listing, UUID(listing_id))).province_code is None
        await backfill(db, apply=True)
        assert (await db.get(Listing, UUID(listing_id))).province_code == "28"


async def test_saved_province_round_trip_alerts_getafe_and_preserves_legacy_city(client, register_user, authoritative_addresses):
    token, tenant = await register_user(client, email="province-alert@example.com")
    headers = {"Authorization": "Bearer " + token}
    _, legacy = await register_user(client, email="legacy-city-alert@example.com")
    legacy_token = (await client.post("/api/v1/auth/login", json={"email": legacy["email"], "password": "Correct-Horse-1234"})).json()["accessToken"]
    for auth, province in [(headers, "28"), ({"Authorization": "Bearer " + legacy_token}, None)]:
        result = await client.post("/api/v1/saved-searches", headers=auth,
            json={"name": "Saved geography", "query": "España" if province else "Madrid", "provinceCode": province,
                  "rentalMode": "long", "filters": {}, "alertsEnabled": True})
        assert result.status_code == 201, result.text
        assert result.json()["provinceCode"] == province
    host_token, host = await register_user(client, email="province-publisher@example.com", role="host")
    ids = []
    async with await direct_client({"Authorization": "Bearer " + host_token}) as direct:
        for row in ADDRESSES:
            assets = await client.seed_listing_assets(host["id"], 5)
            created = await direct.post("/api/v1/listings", json=payload_for(row, assets))
            assert created.status_code == 201, created.text
            ids.append(UUID(created.json()["id"]))
    async with SessionLocal() as db:
        provincial = (await db.scalars(select(Notification.entity_listing_id).where(
            Notification.recipient_user_id == UUID(tenant["id"]), Notification.type == "saved_search_match"))).all()
        city = (await db.scalars(select(Notification.entity_listing_id).where(
            Notification.recipient_user_id == UUID(legacy["id"]), Notification.type == "saved_search_match"))).all()
        assert set(provincial) == set(ids[:2]) and city == ids[:1]
        assert await db.scalar(select(MailOutbox.id).where(MailOutbox.kind == "notification_saved_search_match"))


async def test_legacy_owner_can_verify_address_before_explicit_capacity_checked_backfill(client, register_user, authoritative_addresses):
    from app.commands.backfill_geography import backfill
    token, user = await register_user(client, email="legacy-owner-address@example.com", role="host")
    headers = {"Authorization": "Bearer " + token}
    assets = await client.seed_listing_assets(user["id"], 5)
    async with await direct_client(headers) as direct:
        created = await direct.post("/api/v1/listings", json=payload_for(ADDRESSES[0], assets))
        assert created.status_code == 201, created.text
        listing_id = created.json()["id"]
        async with SessionLocal() as db:
            owner = await db.get(User, UUID(user["id"]))
            owner.municipality_code = owner.address_verified_at = owner.verified_address = None
            now = datetime.now(UTC)
            db.add(ListingPromotion(listing_id=UUID(listing_id), starts_at=now, boosted_at=now, ends_at=now + timedelta(days=1)))
            await db.commit()
        verified = await direct.put("/api/v1/users/me/address", json={"street": "Calle Mayor 1", "postcode": "28013", "city": "Madrid"})
        assert verified.status_code == 200, verified.text
        assert (await direct.get(f"/api/v1/payments/listings/{listing_id}/top/availability")).status_code == 409
        async with SessionLocal() as db:
            report = await backfill(db)
            assert report["topBindings"][0]["municipalityCode"] == "28079"
            assert (await db.get(ListingPromotion, UUID(listing_id))).top_municipality_code is None
            await backfill(db, apply=True, bind_top=True)
        available = await direct.get(f"/api/v1/payments/listings/{listing_id}/top/availability")
        assert available.status_code == 200 and available.json()["availableSlots"] == 2
