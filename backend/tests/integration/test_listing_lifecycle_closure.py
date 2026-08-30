from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from httpx import AsyncClient

from app.db.session import SessionLocal
from app.models import Listing, User
from app.models.moderation import AdminAccess
from app.models.room_details import ListingRoomDetails
from app.services import listings as listing_service

pytestmark = pytest.mark.integration


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def listing_payload(title: str, *, room_capacity: int = 4) -> dict:
    today = datetime.now(UTC).date()
    return {
        "title": title,
        "city": "Adeje",
        "area": "Costa Adeje",
        "street": "Private lifecycle street",
        "postcode": "38660",
        "approximateAddress": "Costa Adeje · ubicación aproximada",
        "rentalMode": "long",
        "monthlyPrice": 700,
        "nightlyPrice": None,
        "weeklyPrice": None,
        "roomType": "Habitación compartida",
        "availableFrom": today.isoformat(),
        "availableUntil": None,
        "minimumStayMonths": 1,
        "minimumNights": None,
        "depositAmount": 700,
        "billsIncluded": True,
        "bathroom": "Baño compartido",
        "kitchen": "Cocina compartida",
        "furnished": True,
        "roomSizeM2": 24,
        "bedroomCount": 4,
        "currentResidents": 2,
        "roomCapacity": room_capacity,
        "shower": "Ducha compartida",
        "homeSizeM2": 100,
        "bathroomCount": 2,
        "rentalUnit": "bed",
        "bedType": "bunk",
        "bedCount": 2,
        "currentRoomResidents": 1,
        "toilet": "Aseo compartido",
        "householdGender": "mixed",
        "householdHasChildren": False,
        "heatingType": "none",
        "accessible": False,
        "floor": "2",
        "couplesAllowed": False,
        "acceptedTenantTypes": ["man", "woman"],
        "tenantRequirement": "any",
        "smokingAllowed": False,
        "petsAllowed": False,
        "childrenAllowed": False,
        "empadronamientoAllowed": True,
        "restrictions": [],
        "amenities": ["Wi-Fi"],
        "latitude": 28.0905,
        "longitude": -16.7358,
        "exactLatitude": 28.091,
        "exactLongitude": -16.735,
        "description": "Deterministic production-moderation lifecycle fixture.",
        "homeDescription": "Shared home.",
        "advertiserType": "Particular",
        "expiresAt": (datetime.now(UTC) + timedelta(days=60)).isoformat(),
    }


async def grant_admin(user_id: str, email: str) -> None:
    async with SessionLocal() as session:
        user = await session.get(User, UUID(user_id))
        assert user is not None
        user.google_subject = f"lifecycle-admin:{user.id}"
        session.add(AdminAccess(email=email.lower(), active=True))
        await session.commit()


async def test_production_moderation_lifecycle_keeps_owner_public_map_and_detail_consistent(
    client: AsyncClient,
    register_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        listing_service,
        "get_settings",
        lambda: type("ProductionListingSettings", (), {"auto_publish_listings": False})(),
    )
    owner_token, _ = await register_user(client, email="closure-owner@example.com", role="host")
    attacker_token, _ = await register_user(client, email="antony502189@gmail.com", role="host")
    admin_token, admin = await register_user(client, email="closure-admin@example.com", role="host")
    await grant_admin(admin["id"], admin["email"])

    created = await client.post(
        "/api/v1/listings",
        headers=auth(owner_token),
        json=listing_payload("Lifecycle closure listing"),
    )
    assert created.status_code == 201, created.text
    listing_id = created.json()["id"]
    assert created.json()["status"] == "pending"
    assert created.json()["roomCapacity"] == 4
    async with SessionLocal() as session:
        stored_listing = await session.get(Listing, UUID(listing_id))
        stored_details = await session.get(ListingRoomDetails, UUID(listing_id))
        assert stored_listing is not None and stored_listing.room_capacity == 2
        assert stored_details is not None and stored_details.room_capacity_v2 == 4

    mine = await client.get("/api/v1/listings/mine", headers=auth(owner_token))
    assert {item["id"]: item["status"] for item in mine.json()}[listing_id] == "pending"
    assert (await client.get(f"/api/v1/listings/{listing_id}")).status_code == 404
    pending_search = await client.post("/api/v1/listings/search", json={"rentalMode": "long"})
    assert listing_id not in {item["id"] for item in pending_search.json()["items"]}

    for method, path, payload in (
        ("patch", f"/api/v1/listings/{listing_id}", {"title": "Foreign edit"}),
        ("patch", f"/api/v1/listings/{listing_id}", {"status": "hidden"}),
        ("post", f"/api/v1/listings/{listing_id}/renew", None),
        ("put", f"/api/v1/listings/{listing_id}/images", {"assetIds": []}),
        ("delete", f"/api/v1/listings/{listing_id}", None),
    ):
        response = await client.request(method.upper(), path, headers=auth(attacker_token), json=payload)
        assert response.status_code == 403, (method, path, response.text)

    approved = await client.patch(
        f"/api/v1/admin/listings/{listing_id}/status",
        headers=auth(admin_token),
        json={"status": "published"},
    )
    assert approved.status_code == 200, approved.text
    public_search = await client.post(
        "/api/v1/listings/search",
        json={
            "rentalMode": "long",
            "roomCapacity": 4,
            "minLatitude": 28.0,
            "maxLatitude": 28.2,
            "minLongitude": -16.8,
            "maxLongitude": -16.6,
        },
    )
    public_ids = {item["id"] for item in public_search.json()["items"]}
    assert listing_id in public_ids
    assert (await client.get(f"/api/v1/listings/{listing_id}")).status_code == 200

    hidden = await client.patch(
        f"/api/v1/listings/{listing_id}", headers=auth(owner_token), json={"status": "hidden"}
    )
    assert hidden.status_code == 200 and hidden.json()["status"] == "hidden"
    assert (await client.get(f"/api/v1/listings/{listing_id}")).status_code == 404
    hidden_search = await client.post("/api/v1/listings/search", json={"rentalMode": "long"})
    assert listing_id not in {item["id"] for item in hidden_search.json()["items"]}
    mine = await client.get("/api/v1/listings/mine", headers=auth(owner_token))
    assert {item["id"]: item["status"] for item in mine.json()}[listing_id] == "hidden"

    resubmitted = await client.patch(
        f"/api/v1/listings/{listing_id}", headers=auth(owner_token), json={"status": "published"}
    )
    assert resubmitted.status_code == 200 and resubmitted.json()["status"] == "pending"
    reapproved = await client.patch(
        f"/api/v1/admin/listings/{listing_id}/status",
        headers=auth(admin_token),
        json={"status": "published"},
    )
    assert reapproved.status_code == 200, reapproved.text

    closed = await client.patch(
        f"/api/v1/listings/{listing_id}", headers=auth(owner_token), json={"status": "closed"}
    )
    assert closed.status_code == 200 and closed.json()["status"] == "closed"
    assert (await client.get(f"/api/v1/listings/{listing_id}")).status_code == 404
    renewed = await client.post(f"/api/v1/listings/{listing_id}/renew", headers=auth(owner_token))
    assert renewed.status_code == 200 and renewed.json()["status"] == "pending"


async def test_admin_must_use_moderation_endpoint_for_status_changes(
    client: AsyncClient,
    register_user,
) -> None:
    owner_token, _ = await register_user(client, email="closure-status-owner@example.com", role="host")
    admin_token, admin = await register_user(client, email="closure-status-admin@example.com", role="host")
    await grant_admin(admin["id"], admin["email"])
    created = await client.post(
        "/api/v1/listings",
        headers=auth(owner_token),
        json=listing_payload("Admin status boundary", room_capacity=2),
    )
    listing_id = created.json()["id"]

    bypass = await client.patch(
        f"/api/v1/listings/{listing_id}", headers=auth(admin_token), json={"status": "closed"}
    )
    assert bypass.status_code == 403
    moderated = await client.patch(
        f"/api/v1/admin/listings/{listing_id}/status",
        headers=auth(admin_token),
        json={"status": "closed"},
    )
    assert moderated.status_code == 200
