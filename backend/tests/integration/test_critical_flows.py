from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import UUID

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import User
from app.models.moderation import AdminAccess, ListingRestriction
from app.services.moderation_expiry import process_expired_moderation

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


async def test_public_catalog_refreshes_after_create_update_hide_and_republish(client: AsyncClient, register_user):
    """The version token must invalidate every user-visible catalog mutation."""
    host_token, _ = await register_user(client, email="catalog-lifecycle@example.com", role="host")
    headers = auth(host_token)

    initial = await client.get("/api/v1/listings/catalog-version")
    assert initial.status_code == 200, initial.text
    initial_version = int(initial.json()["version"])

    created = await client.post(
        "/api/v1/listings",
        headers=headers,
        json=listing_payload(
            title="Catalog lifecycle original title", latitude=28.4701, longitude=-16.2601, bedrooms=3, price=700
        ),
    )
    assert created.status_code == 201, created.text
    listing_id = created.json()["id"]
    created_version = int((await client.get("/api/v1/listings/catalog-version")).json()["version"])
    assert created_version > initial_version
    created_search = await client.post("/api/v1/listings/search", json={"rentalMode": "long"})
    assert listing_id in {item["id"] for item in created_search.json()["items"]}

    updated_title = "Catalog lifecycle updated title"
    updated = await client.patch(f"/api/v1/listings/{listing_id}", headers=headers, json={"title": updated_title})
    assert updated.status_code == 200, updated.text
    updated_version = int((await client.get("/api/v1/listings/catalog-version")).json()["version"])
    assert updated_version > created_version
    updated_search = await client.post("/api/v1/listings/search", json={"rentalMode": "long"})
    assert {item["id"]: item["title"] for item in updated_search.json()["items"]}[listing_id] == updated_title

    hidden = await client.patch(f"/api/v1/listings/{listing_id}", headers=headers, json={"status": "hidden"})
    assert hidden.status_code == 200, hidden.text
    hidden_version = int((await client.get("/api/v1/listings/catalog-version")).json()["version"])
    assert hidden_version > updated_version
    hidden_search = await client.post("/api/v1/listings/search", json={"rentalMode": "long"})
    assert listing_id not in {item["id"] for item in hidden_search.json()["items"]}

    republished = await client.post(f"/api/v1/listings/{listing_id}/renew", headers=headers)
    assert republished.status_code == 200, republished.text
    republished_version = int((await client.get("/api/v1/listings/catalog-version")).json()["version"])
    assert republished_version > hidden_version
    republished_search = await client.post("/api/v1/listings/search", json={"rentalMode": "long"})
    assert listing_id in {item["id"] for item in republished_search.json()["items"]}


async def test_admin_moderation_restrictions_invalidate_the_public_catalog(client: AsyncClient, register_user):
    """Exercise authorization, moderation, expiry and public visibility in one isolated database."""
    admin_token, admin = await register_user(client, email="moderator@example.com", role="admin")
    host_token, host = await register_user(client, email="moderated-host@example.com", role="host")
    admin_headers = auth(admin_token)
    host_headers = auth(host_token)

    non_admin = await client.get("/api/v1/admin/access", headers=host_headers)
    assert non_admin.status_code == 403
    async with SessionLocal() as session:
        stored_admin = await session.get(User, UUID(admin["id"]))
        assert stored_admin is not None
        stored_admin.google_subject = "moderator-google-subject"
        session.add(AdminAccess(email=admin["email"].lower()))
        await session.commit()
    assert (await client.get("/api/v1/admin/access", headers=admin_headers)).status_code == 200

    created = await client.post(
        "/api/v1/listings",
        headers=host_headers,
        json=listing_payload(title="Moderated catalog listing", latitude=28.4801, longitude=-16.2701, bedrooms=2),
    )
    assert created.status_code == 201, created.text
    listing_id = created.json()["id"]
    listing_uuid = UUID(listing_id)

    created_version = int((await client.get("/api/v1/listings/catalog-version")).json()["version"])
    user_restriction = await client.post(
        f"/api/v1/admin/users/{host['id']}/restrictions",
        headers=admin_headers,
        json={"restrictionType": "view_listings", "until": None, "reason": "Repeated public listing policy breach"},
    )
    assert user_restriction.status_code == 200, user_restriction.text
    assert user_restriction.json()["activeRestriction"]["reason"] == "Repeated public listing policy breach"
    user_restriction_version = int((await client.get("/api/v1/listings/catalog-version")).json()["version"])
    assert user_restriction_version > created_version
    hidden_by_user = await client.post("/api/v1/listings/search", json={"rentalMode": "long"})
    assert listing_id not in {item["id"] for item in hidden_by_user.json()["items"]}

    unrestrict_user = await client.delete(f"/api/v1/admin/users/{host['id']}/restrictions/active", headers=admin_headers)
    assert unrestrict_user.status_code == 200, unrestrict_user.text
    user_restore_version = int((await client.get("/api/v1/listings/catalog-version")).json()["version"])
    assert user_restore_version > user_restriction_version
    visible_after_user_restore = await client.post("/api/v1/listings/search", json={"rentalMode": "long"})
    assert listing_id in {item["id"] for item in visible_after_user_restore.json()["items"]}

    until = datetime.now(UTC) + timedelta(days=1)
    listing_restriction = await client.post(
        f"/api/v1/admin/listings/{listing_id}/restrictions",
        headers=admin_headers,
        json={"until": until.isoformat(), "reason": "Listing evidence requires review"},
    )
    assert listing_restriction.status_code == 200, listing_restriction.text
    assert listing_restriction.json()["activeRestriction"]["reason"] == "Listing evidence requires review"
    listing_restriction_version = int((await client.get("/api/v1/listings/catalog-version")).json()["version"])
    assert listing_restriction_version > user_restore_version
    hidden_by_listing = await client.post("/api/v1/listings/search", json={"rentalMode": "long"})
    assert listing_id not in {item["id"] for item in hidden_by_listing.json()["items"]}

    unrestrict_listing = await client.delete(f"/api/v1/admin/listings/{listing_id}/restrictions/active", headers=admin_headers)
    assert unrestrict_listing.status_code == 200, unrestrict_listing.text
    listing_restore_version = int((await client.get("/api/v1/listings/catalog-version")).json()["version"])
    assert listing_restore_version > listing_restriction_version
    visible_after_listing_restore = await client.post("/api/v1/listings/search", json={"rentalMode": "long"})
    assert listing_id in {item["id"] for item in visible_after_listing_restore.json()["items"]}

    expires = await client.post(
        f"/api/v1/admin/listings/{listing_id}/restrictions",
        headers=admin_headers,
        json={"until": until.isoformat(), "reason": "Temporary expiry regression"},
    )
    assert expires.status_code == 200, expires.text
    async with SessionLocal() as session:
        active = await session.scalar(
            select(ListingRestriction).where(
                ListingRestriction.listing_id == listing_uuid,
                ListingRestriction.revoked_at.is_(None),
            )
        )
        assert active is not None
        active.ends_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()
        assert (await process_expired_moderation(session))["listings"] == 1

    expiry_version = int((await client.get("/api/v1/listings/catalog-version")).json()["version"])
    assert expiry_version > listing_restore_version
    visible_after_expiry = await client.post("/api/v1/listings/search", json={"rentalMode": "long"})
    assert listing_id in {item["id"] for item in visible_after_expiry.json()["items"]}
