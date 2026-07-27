from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.main import app
from app.models import (
    AuthSession,
    Favorite,
    MailOutbox,
    MediaAsset,
    SavedSearch,
    SearchHistory,
    User,
)

pytestmark = pytest.mark.integration


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def image_bytes(color: tuple[int, int, int] = (30, 80, 120)) -> bytes:
    output = BytesIO()
    Image.new("RGB", (40, 30), color).save(output, "PNG")
    return output.getvalue()


def listing_payload(*, title: str, available_until: str | None = None) -> dict:
    today = datetime.now(UTC).date()
    return {
        "title": title,
        "city": "Santa Cruz de Tenerife",
        "area": "Centro",
        "street": "Exact private street",
        "postcode": "38001",
        "approximateAddress": "Centro · ubicación aproximada",
        "rentalMode": "long",
        "monthlyPrice": 700,
        "nightlyPrice": None,
        "weeklyPrice": None,
        "roomType": "Habitación individual",
        "availableFrom": (today - timedelta(days=10)).isoformat(),
        "availableUntil": available_until,
        "minimumStayMonths": 1,
        "minimumNights": None,
        "depositAmount": 700,
        "billsIncluded": True,
        "bathroom": "Baño compartido",
        "kitchen": "Cocina compartida",
        "furnished": True,
        "roomSizeM2": 14,
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
        "latitude": 28.463,
        "longitude": -16.252,
        "exactLatitude": 28.464,
        "exactLongitude": -16.251,
        "description": "A complete integration listing used by the second audit regression suite.",
        "homeDescription": "Respect shared spaces.",
        "advertiserType": "Particular",
        "source": "second-audit",
        "expiresAt": (datetime.now(UTC) + timedelta(days=60)).isoformat(),
    }


async def test_old_refresh_token_cannot_be_reused(client: AsyncClient, register_user):
    await register_user(client, email="refresh@example.test")
    old_refresh = client.cookies.get("refresh_token")
    assert old_refresh

    rotated = await client.post("/api/v1/auth/refresh")
    assert rotated.status_code == 200
    current_refresh = client.cookies.get("refresh_token")
    assert current_refresh and current_refresh != old_refresh

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Origin": "http://testserver"},
        cookies={"refresh_token": old_refresh},
    ) as replay:
        rejected = await replay.post("/api/v1/auth/refresh")
    assert rejected.status_code == 401

    family_revoked = await client.post("/api/v1/auth/refresh")
    assert family_revoked.status_code == 401


async def test_availability_window_excludes_already_ended_listing(client: AsyncClient, register_user):
    token, _ = await register_user(client, email="availability@example.test", role="host")
    yesterday = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
    created = await client.post(
        "/api/v1/listings",
        headers=auth(token),
        json=listing_payload(title="Ended availability", available_until=yesterday),
    )
    assert created.status_code == 201, created.text

    search = await client.post(
        "/api/v1/listings/search",
        json={"availableFrom": datetime.now(UTC).date().isoformat(), "limit": 100},
    )
    assert search.status_code == 200, search.text
    assert created.json()["id"] not in {item["id"] for item in search.json()["items"]}


async def test_private_media_cache_and_listing_avatar_separation(client: AsyncClient, register_user):
    token, _ = await register_user(client, email="media@example.test", role="host")
    listing = await client.post(
        "/api/v1/listings",
        headers=auth(token),
        json=listing_payload(title="Media lifecycle listing"),
    )
    assert listing.status_code == 201, listing.text

    upload = await client.post(
        "/api/v1/uploads",
        headers=auth(token),
        files={"file": ("room.png", image_bytes(), "image/png")},
    )
    assert upload.status_code == 201, upload.text
    asset_id = upload.json()["id"]
    media_url = upload.json()["url"]

    private_media = await client.get(media_url, headers=auth(token))
    assert private_media.status_code == 200
    assert private_media.headers["cache-control"] == "private, no-store"
    assert (await client.get(media_url)).status_code == 404

    attached = await client.put(
        f"/api/v1/listings/{listing.json()['id']}/images",
        headers=auth(token),
        json={"assetIds": [asset_id]},
    )
    assert attached.status_code == 200, attached.text

    public_media = await client.get(media_url)
    assert public_media.status_code == 200
    assert public_media.headers["cache-control"].startswith("public")
    etag = public_media.headers["etag"]
    cached = await client.get(media_url, headers={"If-None-Match": etag})
    assert cached.status_code == 304

    avatar_conflict = await client.put(
        "/api/v1/users/me/avatar",
        headers=auth(token),
        json={"assetId": asset_id},
    )
    assert avatar_conflict.status_code == 409


async def test_replacing_and_deleting_listing_cleans_orphaned_media(client: AsyncClient, register_user):
    token, _ = await register_user(client, email="orphan-media@example.test", role="host")
    listing = await client.post(
        "/api/v1/listings",
        headers=auth(token),
        json=listing_payload(title="Orphan media cleanup listing"),
    )
    assert listing.status_code == 201, listing.text
    listing_id = listing.json()["id"]

    first = await client.post(
        "/api/v1/uploads",
        headers=auth(token),
        files={"file": ("first.png", image_bytes((10, 20, 30)), "image/png")},
    )
    second = await client.post(
        "/api/v1/uploads",
        headers=auth(token),
        files={"file": ("second.png", image_bytes((90, 100, 110)), "image/png")},
    )
    assert first.status_code == second.status_code == 201

    attach_first = await client.put(
        f"/api/v1/listings/{listing_id}/images",
        headers=auth(token),
        json={"assetIds": [first.json()["id"]]},
    )
    assert attach_first.status_code == 200
    assert (await client.get(first.json()["url"])).status_code == 200

    replace = await client.put(
        f"/api/v1/listings/{listing_id}/images",
        headers=auth(token),
        json={"assetIds": [second.json()["id"]]},
    )
    assert replace.status_code == 200
    assert (await client.get(first.json()["url"], headers=auth(token))).status_code == 404
    assert (await client.get(second.json()["url"])).status_code == 200

    deleted = await client.delete(f"/api/v1/listings/{listing_id}", headers=auth(token))
    assert deleted.status_code == 204
    assert (await client.get(second.json()["url"], headers=auth(token))).status_code == 404


async def test_disabled_contact_form_blocks_new_threads(client: AsyncClient, register_user):
    host_token, _ = await register_user(client, email="closed-contact@example.test", role="host")
    listing = await client.post(
        "/api/v1/listings",
        headers=auth(host_token),
        json=listing_payload(title="Contact disabled listing"),
    )
    assert listing.status_code == 201
    profile = await client.patch(
        "/api/v1/users/me",
        headers=auth(host_token),
        json={"allowContactForm": False},
    )
    assert profile.status_code == 200

    tenant_token, _ = await register_user(client, email="contact-tenant@example.test")
    message = await client.post(
        "/api/v1/messages",
        headers=auth(tenant_token),
        json={"listingId": listing.json()["id"], "body": "Can I visit?"},
    )
    assert message.status_code == 403


async def test_account_deletion_erases_owned_state(client: AsyncClient, register_user):
    token, user = await register_user(client, email="erase-me@example.test", role="host")
    listing = await client.post(
        "/api/v1/listings",
        headers=auth(token),
        json=listing_payload(title="Account deletion listing"),
    )
    assert listing.status_code == 201
    listing_id = listing.json()["id"]

    assert (await client.put(f"/api/v1/favorites/{listing_id}", headers=auth(token))).status_code == 204
    assert (
        await client.post(
            "/api/v1/saved-searches",
            headers=auth(token),
            json={"name": "Centro", "query": "Centro", "rentalMode": "long", "filters": {}, "polygon": []},
        )
    ).status_code == 201
    assert (
        await client.post("/api/v1/search-history", headers=auth(token), json={"query": "Centro"})
    ).status_code == 204
    upload = await client.post(
        "/api/v1/uploads",
        headers=auth(token),
        files={"file": ("private.png", image_bytes(), "image/png")},
    )
    assert upload.status_code == 201

    deleted = await client.delete("/api/v1/users/me", headers=auth(token))
    assert deleted.status_code == 204

    async with SessionLocal() as session:
        user_id = UUID(user["id"])
        assert await session.scalar(select(func.count()).select_from(AuthSession).where(AuthSession.user_id == user_id)) == 0
        assert await session.scalar(select(func.count()).select_from(Favorite).where(Favorite.user_id == user_id)) == 0
        assert await session.scalar(select(func.count()).select_from(SavedSearch).where(SavedSearch.user_id == user_id)) == 0
        assert await session.scalar(select(func.count()).select_from(SearchHistory).where(SearchHistory.user_id == user_id)) == 0
        assert await session.scalar(select(func.count()).select_from(MailOutbox).where(MailOutbox.recipient == "erase-me@example.test")) == 0
        assert await session.scalar(select(func.count()).select_from(MediaAsset).where(MediaAsset.owner_id == user_id, MediaAsset.deleted_at.is_(None))) == 0
        stored_user = await session.scalar(select(User).where(User.id == user_id))
        assert stored_user is not None
        assert stored_user.email.endswith("@deleted.invalid")
