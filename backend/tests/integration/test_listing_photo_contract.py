from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

pytestmark = pytest.mark.integration


def listing_payload(title: str, asset_ids: list[str]) -> dict:
    return {
        "title": title,
        "city": "Adeje",
        "area": "Centro",
        "approximateAddress": "Centro de Adeje",
        "rentalMode": "long",
        "monthlyPrice": 700,
        "latitude": 28.12,
        "longitude": -16.73,
        "assetIds": asset_ids,
    }


async def test_direct_api_create_and_edit_photo_boundaries(client, register_user):
    token, owner = await register_user(client, email="photo-boundaries@example.com", role="host")
    owner_id = owner["id"]
    assets = await client.seed_listing_assets(owner_id, 40)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Origin": "http://testserver", "Authorization": f"Bearer {token}"},
    ) as direct:
        for count, expected in ((4, 422), (5, 201), (15, 201), (16, 422)):
            response = await direct.post(
                "/api/v1/listings",
                headers={"Idempotency-Key": str(uuid4())},
                json=listing_payload(f"Photo boundary listing {count}", assets[:count] if count != 15 else assets[16:31]),
            )
            assert response.status_code == expected, response.text
            if count == 5:
                listing_id = response.json()["id"]

        for count, expected in ((4, 422), (5, 200), (15, 200), (16, 422)):
            asset_ids = assets[:count] if count != 15 else assets[25:40]
            patch = await direct.patch(f"/api/v1/listings/{listing_id}", json={"assetIds": asset_ids})
            assert patch.status_code == expected, patch.text
            replace = await direct.put(f"/api/v1/listings/{listing_id}/images", json={"assetIds": asset_ids})
            assert replace.status_code == expected, replace.text
