from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from httpx import AsyncClient

from app.db.session import SessionLocal
from app.models import Listing

pytestmark = pytest.mark.integration


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def listing_payload(title: str) -> dict:
    today = datetime.now(UTC).date()
    return {
        "title": title,
        "city": "Adeje",
        "area": "Centro",
        "street": "Private street",
        "postcode": "38670",
        "approximateAddress": "Adeje · ubicación aproximada",
        "rentalMode": "long",
        "monthlyPrice": 650,
        "nightlyPrice": None,
        "weeklyPrice": None,
        "roomType": "Habitación individual",
        "availableFrom": today.isoformat(),
        "availableUntil": None,
        "minimumStayMonths": 1,
        "minimumNights": None,
        "depositAmount": 650,
        "billsIncluded": True,
        "bathroom": "Baño compartido",
        "kitchen": "Cocina compartida",
        "furnished": True,
        "roomSizeM2": 12,
        "bedroomCount": 3,
        "currentResidents": 2,
        "roomCapacity": 1,
        "shower": "Ducha compartida",
        "tenantRequirement": "any",
        "smokingAllowed": False,
        "petsAllowed": False,
        "childrenAllowed": False,
        "empadronamientoAllowed": True,
        "restrictions": [],
        "amenities": ["Wifi"],
        "latitude": 28.1227,
        "longitude": -16.7244,
        "exactLatitude": 28.123,
        "exactLongitude": -16.724,
        "description": "Permanent listing integration fixture.",
        "homeDescription": "Shared home.",
        "advertiserType": "Particular",
        # Old clients may still send this field; the service intentionally
        # ignores it now.
        "expiresAt": (datetime.now(UTC) - timedelta(days=30)).isoformat(),
    }


async def test_past_legacy_expiry_never_hides_or_closes_a_published_listing(
    client: AsyncClient,
    register_user,
) -> None:
    owner_token, _ = await register_user(client, email="permanent-owner@example.com", role="host")

    created = await client.post(
        "/api/v1/listings",
        headers=auth(owner_token),
        json=listing_payload("Room without automatic expiry"),
    )
    assert created.status_code == 201, created.text
    listing_id = UUID(created.json()["id"])
    assert created.json()["status"] == "published"
    assert created.json()["expiresAt"] is None

    # Simulate a legacy production row that still carries a past expires_at.
    async with SessionLocal() as session:
        listing = await session.get(Listing, listing_id)
        assert listing is not None
        listing.expires_at = datetime.now(UTC) - timedelta(days=2)
        await session.commit()

    detail = await client.get(f"/api/v1/listings/{listing_id}")
    assert detail.status_code == 200, detail.text

    search = await client.post("/api/v1/listings/search", json={"rentalMode": "long"})
    assert listing_id in {UUID(item["id"]) for item in search.json()["items"]}

    mine = await client.get("/api/v1/listings/mine", headers=auth(owner_token))
    row = next(item for item in mine.json() if UUID(item["id"]) == listing_id)
    assert row["status"] == "published"
