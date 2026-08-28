from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def listing_payload(*, title: str) -> dict:
    return {
        "title": title,
        "city": "Santa Cruz de Tenerife",
        "area": "Centro",
        "street": "Private street",
        "postcode": "38001",
        "approximateAddress": "Centro · ubicación aproximada",
        "rentalMode": "long",
        "monthlyPrice": 700,
        "nightlyPrice": None,
        "weeklyPrice": None,
        "roomType": "Habitación individual",
        "availableFrom": datetime.now(UTC).date().isoformat(),
        "availableUntil": None,
        "minimumStayMonths": 1,
        "minimumNights": None,
        "depositAmount": 700,
        "billsIncluded": True,
        "bathroom": "Baño compartido",
        "kitchen": "Cocina compartida",
        "furnished": True,
        "roomSizeM2": 14,
        "bedroomCount": 2,
        "currentResidents": 1,
        "roomCapacity": 1,
        "shower": "Ducha compartida",
        "tenantRequirement": "any",
        "smokingAllowed": False,
        "petsAllowed": False,
        "childrenAllowed": False,
        "empadronamientoAllowed": True,
        "restrictions": [],
        "amenities": ["Wifi"],
        "latitude": 28.4636,
        "longitude": -16.2518,
        "exactLatitude": 28.4638,
        "exactLongitude": -16.2516,
        "description": "Regression fixture for logical audit coverage.",
        "homeDescription": "Shared home.",
        "advertiserType": "Particular",
        "expiresAt": (datetime.now(UTC) + timedelta(days=60)).isoformat(),
    }


async def test_guest_listing_views_use_browser_cookie_not_shared_ip(client: AsyncClient, register_user):
    host_token, _ = await register_user(client, email="view-cookie-owner@example.com", role="host")
    created = await client.post(
        "/api/v1/listings",
        headers=auth(host_token),
        json=listing_payload(title="Visitor cookie regression"),
    )
    assert created.status_code == 201, created.text
    listing_id = created.json()["id"]

    client.cookies.set("listing_visitor", "browser-visitor-a", path="/api/v1/listings")
    first = await client.get(f"/api/v1/listings/{listing_id}")
    assert first.status_code == 200, first.text
    assert first.json()["views"] == 1

    # Same test client means the same network identity. A second durable browser
    # token must still count as a separate visitor behind shared NAT/Wi-Fi.
    client.cookies.set("listing_visitor", "browser-visitor-b", path="/api/v1/listings")
    second = await client.get(f"/api/v1/listings/{listing_id}")
    assert second.status_code == 200, second.text
    assert second.json()["views"] == 2

    repeated = await client.get(f"/api/v1/listings/{listing_id}")
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["views"] == 2


async def test_account_deletion_invalidates_catalog_and_removes_owned_listing(client: AsyncClient, register_user):
    host_token, _ = await register_user(client, email="catalog-delete-owner@example.com", role="host")
    created = await client.post(
        "/api/v1/listings",
        headers=auth(host_token),
        json=listing_payload(title="Account deletion catalog regression"),
    )
    assert created.status_code == 201, created.text
    listing_id = created.json()["id"]

    before = await client.get("/api/v1/listings/catalog-version")
    assert before.status_code == 200, before.text
    before_version = int(before.json()["version"])

    deleted = await client.delete("/api/v1/users/me", headers=auth(host_token))
    assert deleted.status_code == 204, deleted.text

    after = await client.get("/api/v1/listings/catalog-version")
    assert after.status_code == 200, after.text
    assert int(after.json()["version"]) > before_version

    public_search = await client.post("/api/v1/listings/search", json={"rentalMode": "long"})
    assert public_search.status_code == 200, public_search.text
    assert listing_id not in {item["id"] for item in public_search.json()["items"]}
    assert (await client.get(f"/api/v1/listings/{listing_id}")).status_code == 404


async def test_public_profile_changes_invalidate_catalog_and_refresh_listing_contacts(client: AsyncClient, register_user):
    host_token, _ = await register_user(client, email="catalog-profile-owner@example.com", role="host")
    created = await client.post(
        "/api/v1/listings",
        headers=auth(host_token),
        json=listing_payload(title="Profile catalog regression"),
    )
    assert created.status_code == 201, created.text
    listing_id = created.json()["id"]

    before = await client.get("/api/v1/listings/catalog-version")
    assert before.status_code == 200, before.text
    before_version = int(before.json()["version"])

    updated = await client.patch(
        "/api/v1/users/me",
        headers=auth(host_token),
        json={
            "name": "Updated Public Owner",
            "phone": "+34600000123",
            "showPhone": True,
        },
    )
    assert updated.status_code == 200, updated.text

    after = await client.get("/api/v1/listings/catalog-version")
    assert after.status_code == 200, after.text
    assert int(after.json()["version"]) > before_version

    public_search = await client.post("/api/v1/listings/search", json={"rentalMode": "long"})
    assert public_search.status_code == 200, public_search.text
    public_listing = next(item for item in public_search.json()["items"] if item["id"] == listing_id)
    assert public_listing["owner"]["name"] == "Updated Public Owner"
    assert public_listing["contactPhone"] == "+34600000123"
    assert public_listing["showPhone"] is True
