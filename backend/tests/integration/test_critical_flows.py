from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest
from httpx import AsyncClient
from PIL import Image

pytestmark = pytest.mark.integration


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def listing_payload(*, title: str, latitude: float, longitude: float, bedrooms: int, price: int = 600) -> dict:
    return {
        "title": title,
        "city": "Santa Cruz de Tenerife",
        "area": "Centro",
        "street": "Private street",
        "postcode": "38001",
        "approximateAddress": "Centro · ubicación aproximada",
        "rentalMode": "long",
        "monthlyPrice": price,
        "nightlyPrice": None,
        "weeklyPrice": None,
        "roomType": "Habitación individual",
        "availableFrom": datetime.now(UTC).date().isoformat(),
        "availableUntil": None,
        "minimumStayMonths": 1,
        "minimumNights": None,
        "depositAmount": price,
        "billsIncluded": True,
        "bathroom": "Baño compartido",
        "kitchen": "Cocina compartida",
        "furnished": True,
        "roomSizeM2": 14,
        "bedroomCount": bedrooms,
        "currentResidents": 2,
        "roomCapacity": 1,
        "shower": "Ducha compartida",
        "tenantRequirement": "any",
        "smokingAllowed": False,
        "petsAllowed": False,
        "childrenAllowed": False,
        "empadronamientoAllowed": True,
        "restrictions": ["No fumar"],
        "amenities": ["Wifi"],
        "latitude": latitude,
        "longitude": longitude,
        "exactLatitude": latitude + 0.0004,
        "exactLongitude": longitude + 0.0004,
        "description": "Integration listing with enough information for the complete critical flow.",
        "homeDescription": "Respect the shared home.",
        "advertiserType": "Particular",
        "source": "integration-test",
        "expiresAt": (datetime.now(UTC) + timedelta(days=60)).isoformat(),
    }


def image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (64, 48), (120, 160, 200)).save(output, "PNG")
    return output.getvalue()


async def test_complete_auth_geo_media_message_and_delete_flow(client: AsyncClient, register_user):
    host_token, host = await register_user(client, email="host@example.com", role="host")

    refresh = await client.post("/api/v1/auth/refresh")
    assert refresh.status_code == 200, refresh.text
    assert refresh.json()["user"]["id"] == host["id"]

    inside = await client.post(
        "/api/v1/listings",
        headers=auth(host_token),
        json=listing_payload(title="Inside polygon", latitude=28.1000, longitude=-16.7000, bedrooms=3, price=650),
    )
    outside = await client.post(
        "/api/v1/listings",
        headers=auth(host_token),
        json=listing_payload(title="Outside polygon", latitude=28.3000, longitude=-16.3000, bedrooms=12, price=850),
    )
    assert inside.status_code == outside.status_code == 201
    inside_id = inside.json()["id"]
    outside_id = outside.json()["id"]
    assert "street" in inside.json()

    public_detail = await client.get(f"/api/v1/listings/{inside_id}")
    assert public_detail.status_code == 200
    assert "street" not in public_detail.json()
    assert "postcode" not in public_detail.json()
    assert "exactLatitude" not in public_detail.json()

    polygon = await client.post(
        "/api/v1/listings/search",
        json={
            "rentalMode": "long",
            "bedroomCounts": [3],
            "polygon": [
                {"latitude": 28.05, "longitude": -16.75},
                {"latitude": 28.15, "longitude": -16.75},
                {"latitude": 28.15, "longitude": -16.65},
                {"latitude": 28.05, "longitude": -16.65},
            ],
        },
    )
    assert polygon.status_code == 200, polygon.text
    assert [item["id"] for item in polygon.json()["items"]] == [inside_id]

    more_than_ten = await client.post(
        "/api/v1/listings/search",
        json={"rentalMode": "long", "bedroomCounts": ["10+"]},
    )
    assert more_than_ten.status_code == 200
    assert [item["id"] for item in more_than_ten.json()["items"]] == [outside_id]

    upload = await client.post(
        "/api/v1/uploads",
        headers=auth(host_token),
        files={"file": ("avatar.png", image_bytes(), "image/png")},
    )
    assert upload.status_code == 201, upload.text
    asset_id = upload.json()["id"]
    avatar = await client.put(
        "/api/v1/users/me/avatar",
        headers=auth(host_token),
        json={"assetId": asset_id},
    )
    assert avatar.status_code == 200
    assert avatar.json()["avatarUrl"].endswith(asset_id)
    public_avatar = await client.get(avatar.json()["avatarUrl"])
    assert public_avatar.status_code == 200
    assert public_avatar.headers["content-type"] == "image/webp"
    attached_delete = await client.delete(f"/api/v1/uploads/{asset_id}", headers=auth(host_token))
    assert attached_delete.status_code == 409

    tenant_token, _ = await register_user(client, email="tenant@example.com", role="tenant")
    initial_message = await client.post(
        "/api/v1/messages",
        headers=auth(tenant_token),
        json={"listingId": inside_id, "body": "Hello from the integration test"},
    )
    assert initial_message.status_code == 201, initial_message.text

    host_threads = await client.get("/api/v1/messages/threads", headers=auth(host_token))
    assert host_threads.status_code == 200
    assert len(host_threads.json()) == 1
    thread_id = host_threads.json()[0]["id"]
    reply = await client.post(
        f"/api/v1/messages/threads/{thread_id}",
        headers=auth(host_token),
        json={"body": "Host reply"},
    )
    assert reply.status_code == 201
    tenant_messages = await client.get(f"/api/v1/messages/threads/{thread_id}", headers=auth(tenant_token))
    assert tenant_messages.status_code == 200
    assert [message["body"] for message in tenant_messages.json()] == [
        "Hello from the integration test",
        "Host reply",
    ]
    assert tenant_messages.json()[-1]["readAt"] is not None

    delete_account = await client.delete("/api/v1/users/me", headers=auth(tenant_token))
    assert delete_account.status_code == 204
    deleted_me = await client.get("/api/v1/users/me", headers=auth(tenant_token))
    assert deleted_me.status_code == 401

    clear_avatar = await client.put(
        "/api/v1/users/me/avatar",
        headers=auth(host_token),
        json={"assetId": None},
    )
    assert clear_avatar.status_code == 200
    assert clear_avatar.json()["avatarUrl"] is None
    assert (await client.get(f"/api/v1/media/{asset_id}")).status_code == 404
