from uuid import UUID

import pytest
from httpx import AsyncClient
from test_listing_lifecycle_closure import auth, listing_payload

from app.db.session import SessionLocal
from app.models import Listing

pytestmark = pytest.mark.integration


async def test_price_limit_across_create_patch_renew_and_public_visibility(client: AsyncClient, register_user):
    token, _ = await register_user(client, email="price-cap-owner@example.com", role="host")
    headers = auth(token)
    payload = listing_payload("Long term boundary") | {"monthlyPrice": 1000}
    created = await client.post("/api/v1/listings", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    listing_id = created.json()["id"]
    assert (await client.get(f"/api/v1/listings/{listing_id}")).status_code == 200
    rejected = await client.post("/api/v1/listings", headers=headers, json=payload | {"monthlyPrice": 1001})
    assert rejected.status_code == 422
    patched = await client.patch(f"/api/v1/listings/{listing_id}", headers=headers, json={"monthlyPrice": 1001})
    assert patched.status_code == 422

    holiday = await client.post(
        "/api/v1/listings",
        headers=headers,
        json=listing_payload("Holiday above cap")
        | {
            "rentalMode": "holiday",
            "monthlyPrice": 5000,
            "nightlyPrice": 2000,
            "weeklyPrice": 7000,
        },
    )
    assert holiday.status_code == 201, holiday.text
    holiday_id = holiday.json()["id"]
    assert (await client.get(f"/api/v1/listings/{holiday_id}")).status_code == 200
    assert (
        await client.patch(
            f"/api/v1/listings/{holiday_id}", headers=headers, json={"nightlyPrice": 3000, "monthlyPrice": 9000}
        )
    ).status_code == 200
    assert (await client.post(f"/api/v1/listings/{holiday_id}/renew", headers=headers)).status_code == 200
    assert (
        await client.patch(f"/api/v1/listings/{holiday_id}", headers=headers, json={"rentalMode": "long"})
    ).status_code == 422

    # Legacy over-limit rows disappear publicly, remain owned, and can be withdrawn/repaired.
    async with SessionLocal() as session:
        listing = await session.get(Listing, UUID(listing_id))
        listing.monthly_price = 1001
        await session.commit()
    assert (await client.get(f"/api/v1/listings/{listing_id}")).status_code == 404
    catalog = await client.post("/api/v1/listings/search", json={"rentalMode": "long"})
    assert listing_id not in {item["id"] for item in catalog.json()["items"]}
    mine = await client.get("/api/v1/listings/mine", headers=headers)
    assert listing_id in {item["id"] for item in mine.json()}
    assert (await client.post(f"/api/v1/listings/{listing_id}/renew", headers=headers)).status_code == 422
    assert (
        await client.patch(f"/api/v1/listings/{listing_id}", headers=headers, json={"status": "hidden"})
    ).status_code == 200
    assert (
        await client.patch(f"/api/v1/listings/{listing_id}", headers=headers, json={"monthlyPrice": 1000})
    ).status_code == 200
    assert (await client.post(f"/api/v1/listings/{listing_id}/renew", headers=headers)).status_code == 200
