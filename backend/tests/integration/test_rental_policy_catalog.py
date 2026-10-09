from uuid import UUID

import pytest
from test_listing_lifecycle_closure import auth, listing_payload

from app.db.session import SessionLocal
from app.models import Listing

pytestmark = pytest.mark.integration


async def test_manual_writes_and_all_public_projections(client, register_user):
    token, _ = await register_user(client, email="policy@example.com", role="host")
    headers = auth(token)
    valid = listing_payload("Verified rental at the inclusive ceiling") | {"monthlyPrice": 1000}
    created = await client.post("/api/v1/listings", json=valid, headers=headers)
    assert created.status_code == 201, created.text
    listing_id = created.json()["id"]
    for price in (1001, 1500, 0, -1, None):
        response = await client.post("/api/v1/listings", json=valid | {"monthlyPrice": price}, headers=headers)
        assert response.status_code == 422, response.text
        response = await client.patch(f"/api/v1/listings/{listing_id}", json={"monthlyPrice": price}, headers=headers)
        assert response.status_code == 422, response.text
    # Simulate untouched legacy production data, without changing the writer contract.
    async with SessionLocal() as session:
        row = await session.get(Listing, UUID(listing_id))
        row.monthly_price = 1250
        await session.commit()
    for path in (f"/api/v1/listings/{listing_id}", f"/api/v1/listings/{listing_id}/images"):
        response = await client.get(path)
        assert response.status_code == 404, response.text
    response = await client.post(f"/api/v1/listings/{listing_id}/renew", headers=headers)
    assert response.status_code == 422, response.text
    response = await client.patch(f"/api/v1/listings/{listing_id}", json={"title": "Unchanged invalid rent"}, headers=headers)
    assert response.status_code == 422, response.text
    response = await client.post("/api/v1/listings/search", json={})
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 0
    response = await client.post("/api/v1/listings/search/cards", json={})
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 0
    response = await client.patch(f"/api/v1/listings/{listing_id}", json={"monthlyPrice": 1000}, headers=headers)
    assert response.status_code == 200, response.text
    response = await client.get(f"/api/v1/listings/{listing_id}")
    assert response.status_code == 200, response.text
