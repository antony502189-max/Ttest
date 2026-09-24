from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import UUID

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import (
    AuditLog,
    DiscardedListing,
    ExternalListingSource,
    Favorite,
    Listing,
    ListingImage,
    ListingStatusHistory,
    ListingView,
    MailOutbox,
    MediaAsset,
    Message,
    MessageThread,
    Notification,
    Report,
    User,
)
from app.models.moderation import AdminAccess, HomepageHeroPromotion, ListingPromotion, ListingRestriction
from app.models.room_details import ListingRoomDetails
from app.models.storage_deletion import StorageDeletionJob
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
    host_token = refresh.json()["accessToken"]

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


async def test_listing_owner_can_hard_delete_local_listing_and_dependents(client: AsyncClient, register_user):
    owner_token, owner = await register_user(client, email="delete-owner@example.com", role="host")
    foreign_token, foreign = await register_user(client, email="delete-foreign@example.com", role="host")

    upload = await client.post(
        "/api/v1/uploads",
        headers=auth(owner_token),
        files={"file": ("delete-room.png", image_bytes(), "image/png")},
    )
    assert upload.status_code == 201, upload.text
    asset_id = upload.json()["id"]
    asset_uuid = UUID(asset_id)
    async with SessionLocal() as session:
        uploaded_asset = await session.get(MediaAsset, asset_uuid)
        assert uploaded_asset is not None
        storage_key = uploaded_asset.storage_key

    payload = listing_payload(title="Owner delete target", latitude=28.4711, longitude=-16.2611, bedrooms=2)
    payload["assetIds"] = [asset_id]
    created = await client.post("/api/v1/listings", headers=auth(owner_token), json=payload)
    assert created.status_code == 201, created.text
    listing_id = created.json()["id"]
    listing_uuid = UUID(listing_id)

    async with SessionLocal() as session:
        creation_notification = await session.scalar(
            select(Notification).where(Notification.entity_listing_id == listing_uuid)
        )
        creation_mail = await session.scalar(
            select(MailOutbox).where(MailOutbox.body.contains(f"/habitacion/{listing_id}"))
        )
        assert creation_notification is not None
        assert creation_mail is not None
        creation_notification_id = creation_notification.id
        creation_mail_id = creation_mail.id
        session.add(
            AuditLog(
                actor_id=UUID(owner["id"]),
                action="listing.test_history",
                target_type="listing",
                target_id=listing_uuid,
                detail={"test": True},
            )
        )
        session.add(Favorite(user_id=UUID(foreign["id"]), listing_id=listing_uuid))
        session.add(DiscardedListing(user_id=UUID(foreign["id"]), listing_id=listing_uuid))
        session.add(ListingView(listing_id=listing_uuid, viewer_key="delete-regression", view_date=datetime.now(UTC).date()))
        session.add(
            Report(
                public_reference=f"R-{str(listing_uuid).replace('-', '')[:10]}",
                listing_id=listing_uuid,
                reporter_id=UUID(foreign["id"]),
                reason="delete regression",
                comment="must cascade",
            )
        )
        session.add(ListingRestriction(listing_id=listing_uuid, reason="delete regression"))
        session.add(ListingPromotion(listing_id=listing_uuid, boosted_by=UUID(owner["id"])))
        thread = MessageThread(
            listing_id=listing_uuid,
            tenant_id=UUID(foreign["id"]),
            host_id=UUID(owner["id"]),
        )
        session.add(thread)
        await session.flush()
        thread_id = thread.id
        message = Message(
            thread_id=thread_id,
            sender_id=UUID(foreign["id"]),
            body="delete cascade regression",
        )
        session.add(message)
        await session.flush()
        message_id = message.id
        session.add(
            HomepageHeroPromotion(
                id=1,
                listing_id=listing_uuid,
                starts_at=datetime.now(UTC),
                ends_at=datetime.now(UTC) + timedelta(days=1),
                configured_by=UUID(owner["id"]),
            )
        )
        await session.commit()

    denied = await client.delete(f"/api/v1/listings/{listing_id}", headers=auth(foreign_token))
    assert denied.status_code == 403, denied.text
    async with SessionLocal() as session:
        assert await session.get(Listing, listing_uuid) is not None

    deleted = await client.delete(f"/api/v1/listings/{listing_id}", headers=auth(owner_token))
    assert deleted.status_code == 204, deleted.text
    assert (await client.get(f"/api/v1/listings/{listing_id}")).status_code == 404
    mine = await client.get("/api/v1/listings/mine", headers=auth(owner_token))
    assert listing_id not in {item["id"] for item in mine.json()}

    async with SessionLocal() as session:
        assert await session.get(Listing, listing_uuid) is None
        assert await session.get(ListingRoomDetails, listing_uuid) is None
        assert await session.get(MediaAsset, asset_uuid) is None
        assert await session.scalar(
            select(StorageDeletionJob).where(StorageDeletionJob.storage_key == storage_key)
        ) is not None
        assert not list(await session.scalars(select(ListingImage).where(ListingImage.listing_id == listing_uuid)))
        assert not list(
            await session.scalars(select(ListingStatusHistory).where(ListingStatusHistory.listing_id == listing_uuid))
        )
        assert not list(await session.scalars(select(Favorite).where(Favorite.listing_id == listing_uuid)))
        assert not list(await session.scalars(select(DiscardedListing).where(DiscardedListing.listing_id == listing_uuid)))
        assert not list(await session.scalars(select(ListingView).where(ListingView.listing_id == listing_uuid)))
        assert not list(await session.scalars(select(Report).where(Report.listing_id == listing_uuid)))
        assert await session.get(MessageThread, thread_id) is None
        assert await session.get(Message, message_id) is None
        assert not list(
            await session.scalars(select(ListingRestriction).where(ListingRestriction.listing_id == listing_uuid))
        )
        assert await session.get(ListingPromotion, listing_uuid) is None
        assert not list(
            await session.scalars(select(HomepageHeroPromotion).where(HomepageHeroPromotion.listing_id == listing_uuid))
        )
        assert await session.scalar(select(AuditLog).where(AuditLog.target_id == listing_uuid)) is None
        assert await session.get(Notification, creation_notification_id) is None
        assert await session.get(MailOutbox, creation_mail_id) is None
        assert await session.scalar(
            select(Notification).where(
                Notification.recipient_user_id == UUID(owner["id"]),
                Notification.type == "listing_deleted",
            )
        ) is None
        assert await session.scalar(
            select(Notification).where(
                Notification.recipient_user_id == UUID(foreign["id"]),
                Notification.type == "favorite_unavailable",
            )
        ) is None


async def test_active_admin_can_hard_delete_another_owners_local_listing(client: AsyncClient, register_user):
    owner_token, owner = await register_user(client, email="admin-delete-owner@example.com", role="host")
    admin_token, admin = await register_user(client, email="admin-delete-operator@example.com", role="host")
    async with SessionLocal() as session:
        stored_admin = await session.get(User, UUID(admin["id"]))
        assert stored_admin is not None
        stored_admin.google_subject = "admin-delete-google-subject"
        session.add(AdminAccess(email=admin["email"].lower()))
        await session.commit()

    created = await client.post(
        "/api/v1/listings",
        headers=auth(owner_token),
        json=listing_payload(title="Admin delete target", latitude=28.4721, longitude=-16.2621, bedrooms=2),
    )
    assert created.status_code == 201, created.text
    listing_id = created.json()["id"]
    listing_uuid = UUID(listing_id)

    owner_mine = await client.get("/api/v1/listings/mine", headers=auth(owner_token))
    assert listing_id in {item["id"] for item in owner_mine.json()}
    admin_mine = await client.get("/api/v1/listings/mine", headers=auth(admin_token))
    assert listing_id not in {item["id"] for item in admin_mine.json()}

    async with SessionLocal() as session:
        creation_notification = await session.scalar(
            select(Notification).where(Notification.entity_listing_id == listing_uuid)
        )
        assert creation_notification is not None
        creation_notification_id = creation_notification.id

    deleted = await client.delete(f"/api/v1/listings/{listing_id}", headers=auth(admin_token))
    assert deleted.status_code == 204, deleted.text

    admin_rows = await client.get("/api/v1/admin/listings", headers=auth(admin_token))
    assert admin_rows.status_code == 200, admin_rows.text
    assert listing_id not in {item["id"] for item in admin_rows.json()}

    async with SessionLocal() as session:
        assert await session.get(Listing, listing_uuid) is None
        assert await session.scalar(select(AuditLog).where(AuditLog.target_id == listing_uuid)) is None
        assert await session.get(Notification, creation_notification_id) is None
        notification = await session.scalar(
            select(Notification)
            .where(
                Notification.recipient_user_id == UUID(owner["id"]),
                Notification.type == "listing_deleted",
            )
            .order_by(Notification.created_at.desc())
        )
        assert notification is not None
        assert notification.entity_listing_id is None
        assert notification.title == "Tu anuncio fue eliminado por un administrador"
        assert notification.body == "Tu anuncio fue eliminado por un administrador."
        assert listing_id not in notification.idempotency_key


async def test_imported_listing_cannot_be_deleted_by_owner_or_admin(client: AsyncClient, register_user):
    owner_token, _owner = await register_user(client, email="external-delete-owner@example.com", role="host")
    admin_token, admin = await register_user(client, email="external-delete-admin@example.com", role="host")
    async with SessionLocal() as session:
        stored_admin = await session.get(User, UUID(admin["id"]))
        assert stored_admin is not None
        stored_admin.google_subject = "external-delete-admin-google-subject"
        session.add(AdminAccess(email=admin["email"].lower()))
        await session.commit()

    created = await client.post(
        "/api/v1/listings",
        headers=auth(owner_token),
        json=listing_payload(title="Imported delete protection", latitude=28.4731, longitude=-16.2631, bedrooms=2),
    )
    assert created.status_code == 201, created.text
    listing_id = created.json()["id"]
    listing_uuid = UUID(listing_id)

    async with SessionLocal() as session:
        listing = await session.get(Listing, listing_uuid)
        assert listing is not None
        listing.is_external = True
        listing.primary_source = "test-parser"
        listing.primary_source_url = "https://example.invalid/imported-listing"
        await session.commit()

    owner_delete = await client.delete(f"/api/v1/listings/{listing_id}", headers=auth(owner_token))
    assert owner_delete.status_code == 409, owner_delete.text
    assert owner_delete.json()["code"] == "EXTERNAL_LISTING_DELETE_FORBIDDEN"

    admin_delete = await client.delete(f"/api/v1/listings/{listing_id}", headers=auth(admin_token))
    assert admin_delete.status_code == 409, admin_delete.text
    assert admin_delete.json()["code"] == "EXTERNAL_LISTING_DELETE_FORBIDDEN"

    async with SessionLocal() as session:
        listing = await session.get(Listing, listing_uuid)
        assert listing is not None
        assert listing.is_external is True
        assert listing.deleted_at is None

    source_backed = await client.post(
        "/api/v1/listings",
        headers=auth(owner_token),
        json=listing_payload(title="Source marker delete protection", latitude=28.4741, longitude=-16.2641, bedrooms=2),
    )
    assert source_backed.status_code == 201, source_backed.text
    source_backed_id = source_backed.json()["id"]
    source_backed_uuid = UUID(source_backed_id)

    async with SessionLocal() as session:
        listing = await session.get(Listing, source_backed_uuid)
        assert listing is not None
        assert listing.is_external is False
        session.add(
            ExternalListingSource(
                source_name="test-parser",
                external_id="source-backed-delete-protection",
                source_url="https://example.invalid/source-backed-delete-protection",
                canonical_listing_id=source_backed_uuid,
                raw_payload={},
                normalized_payload={},
                fingerprint="source-backed-delete-protection",
            )
        )
        await session.commit()

    source_owner_delete = await client.delete(f"/api/v1/listings/{source_backed_id}", headers=auth(owner_token))
    assert source_owner_delete.status_code == 409, source_owner_delete.text
    assert source_owner_delete.json()["code"] == "EXTERNAL_LISTING_DELETE_FORBIDDEN"

    source_admin_delete = await client.delete(f"/api/v1/listings/{source_backed_id}", headers=auth(admin_token))
    assert source_admin_delete.status_code == 409, source_admin_delete.text
    assert source_admin_delete.json()["code"] == "EXTERNAL_LISTING_DELETE_FORBIDDEN"

    async with SessionLocal() as session:
        assert await session.get(Listing, source_backed_uuid) is not None
        assert await session.scalar(
            select(ExternalListingSource.id).where(
                ExternalListingSource.canonical_listing_id == source_backed_uuid
            )
        ) is not None


async def test_admin_renewal_notifies_the_listing_owner(client: AsyncClient, register_user):
    owner_token, owner = await register_user(client, email="renewal-owner@example.com", role="host")
    admin_token, admin = await register_user(client, email="renewal-admin@example.com", role="host")
    async with SessionLocal() as session:
        stored_admin = await session.get(User, UUID(admin["id"]))
        assert stored_admin is not None
        stored_admin.google_subject = "renewal-admin-google-subject"
        session.add(AdminAccess(email=admin["email"].lower()))
        await session.commit()

    created = await client.post(
        "/api/v1/listings",
        headers=auth(owner_token),
        json=listing_payload(title="Admin renewed owner listing", latitude=28.4721, longitude=-16.2621, bedrooms=2),
    )
    assert created.status_code == 201, created.text
    listing_id = UUID(created.json()["id"])
    closed = await client.patch(f"/api/v1/listings/{listing_id}", headers=auth(owner_token), json={"status": "closed"})
    assert closed.status_code == 200, closed.text

    renewed = await client.post(f"/api/v1/listings/{listing_id}/renew", headers=auth(admin_token))
    assert renewed.status_code == 200, renewed.text

    async with SessionLocal() as session:
        notifications = list(
            await session.scalars(
                select(Notification).where(
                    Notification.entity_listing_id == listing_id,
                    Notification.type == "listing_republished",
                )
            )
        )
    assert [notification.recipient_user_id for notification in notifications] == [UUID(owner["id"])]


async def test_designated_administrators_require_google_identity_before_server_access(client: AsyncClient, register_user):
    designated = ("antony502189@gmail.com", "tf.shuler@gmail.com")
    sessions = []
    for email in designated:
        token, user = await register_user(client, email=email, role="host")
        sessions.append((token, user))
    async with SessionLocal() as session:
        for _, user in sessions:
            session.add(AdminAccess(email=user["email"].lower(), active=True))
        await session.commit()

    # The allowlist grant alone is not authority: a password-only designated
    # The signed-in designated account receives a self-only repair path; this
    # does not reveal grants for any other email address.
    needs_google = await client.get("/api/v1/admin/access", headers=auth(sessions[0][0]))
    assert needs_google.status_code == 403
    assert needs_google.json()["code"] == "GOOGLE_IDENTITY_REQUIRED"

    async with SessionLocal() as session:
        for _, user in sessions:
            stored = await session.get(User, UUID(user["id"]))
            assert stored is not None
            stored.google_subject = f"google-subject:{stored.id}"
        await session.commit()

    for token, _ in sessions:
        assert (await client.get("/api/v1/admin/access", headers=auth(token))).status_code == 200

    normal_token, _ = await register_user(client, email="ordinary-google-user@example.com", role="host")
    normal = await client.get("/api/v1/admin/access", headers=auth(normal_token))
    assert normal.status_code == 403
    assert normal.json()["code"] == "ADMIN_ACCESS_DENIED"


async def test_admin_moderation_restrictions_invalidate_the_public_catalog(client: AsyncClient, register_user):
    """Exercise authorization, moderation, expiry and public visibility in one isolated database."""
    # Registration intentionally permits only product roles. Server-side
    # AdminAccess, not the product role, grants administration capabilities.
    admin_token, admin = await register_user(client, email="moderator@example.com", role="host")
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

    low_price = await client.post(
        "/api/v1/listings",
        headers=host_headers,
        json=listing_payload(
            title="Low-price ordinary listing", latitude=28.4701, longitude=-16.2601, bedrooms=2, price=100
        ),
    )
    high_price = await client.post(
        "/api/v1/listings",
        headers=host_headers,
        json=listing_payload(
            title="High-price ordinary listing", latitude=28.4751, longitude=-16.2651, bedrooms=2, price=1000
        ),
    )
    assert low_price.status_code == high_price.status_code == 201

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

    unrestrict_user = await client.delete(
        f"/api/v1/admin/users/{host['id']}/restrictions/active", headers=admin_headers
    )
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

    unrestrict_listing = await client.delete(
        f"/api/v1/admin/listings/{listing_id}/restrictions/active", headers=admin_headers
    )
    assert unrestrict_listing.status_code == 200, unrestrict_listing.text
    listing_restore_version = int((await client.get("/api/v1/listings/catalog-version")).json()["version"])
    assert listing_restore_version > listing_restriction_version
    visible_after_listing_restore = await client.post("/api/v1/listings/search", json={"rentalMode": "long"})
    assert listing_id in {item["id"] for item in visible_after_listing_restore.json()["items"]}

    permanent = await client.post(
        f"/api/v1/admin/listings/{listing_id}/restrictions",
        headers=admin_headers,
        json={"until": None, "reason": "Permanent public policy breach"},
    )
    assert permanent.status_code == 200, permanent.text
    assert permanent.json()["activeRestriction"]["endsAt"] is None
    assert listing_id not in {
        item["id"] for item in (await client.post("/api/v1/listings/search", json={"rentalMode": "long"})).json()["items"]
    }
    async with SessionLocal() as session:
        permanent_row = await session.scalar(
            select(ListingRestriction).where(
                ListingRestriction.listing_id == listing_uuid,
                ListingRestriction.revoked_at.is_(None),
                ListingRestriction.ends_at.is_(None),
            )
        )
        assert permanent_row is not None
        assert (await process_expired_moderation(session))["listings"] == 0

    manually_unrestricted = await client.delete(
        f"/api/v1/admin/listings/{listing_id}/restrictions/active", headers=admin_headers
    )
    assert manually_unrestricted.status_code == 200, manually_unrestricted.text
    assert listing_id in {
        item["id"] for item in (await client.post("/api/v1/listings/search", json={"rentalMode": "long"})).json()["items"]
    }

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
        active.starts_at = datetime.now(UTC) - timedelta(days=2)
        active.ends_at = datetime.now(UTC) - timedelta(days=1)
        await session.commit()
        assert (await process_expired_moderation(session))["listings"] == 1

    expiry_version = int((await client.get("/api/v1/listings/catalog-version")).json()["version"])
    assert expiry_version > listing_restore_version
    visible_after_expiry = await client.post("/api/v1/listings/search", json={"rentalMode": "long"})
    assert listing_id in {item["id"] for item in visible_after_expiry.json()["items"]}

    promoted = await client.put(f"/api/v1/admin/listings/{listing_id}/promotion", headers=admin_headers)
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["promoted"] is True
    first_boosted_at = promoted.json()["boostedAt"]
    assert first_boosted_at
    re_promoted = await client.put(f"/api/v1/admin/listings/{listing_id}/promotion", headers=admin_headers)
    assert re_promoted.status_code == 200, re_promoted.text
    assert re_promoted.json()["promoted"] is True
    public_after_promotion = await client.post("/api/v1/listings/search", json={"rentalMode": "long"})
    assert public_after_promotion.json()["items"][0]["id"] == listing_id
    assert public_after_promotion.json()["items"][0]["promoted"] is True
    for sort in ("newest", "oldest", "price_asc", "price_desc"):
        sorted_page = await client.post(
            "/api/v1/listings/search",
            json={"rentalMode": "long", "sort": sort, "limit": 1, "offset": 0},
        )
        assert sorted_page.status_code == 200, sorted_page.text
        assert sorted_page.json()["items"][0]["id"] == listing_id
        assert sorted_page.json()["items"][0]["promoted"] is True
    async with SessionLocal() as session:
        assert (
            await session.scalar(select(ListingPromotion).where(ListingPromotion.listing_id == listing_uuid))
            is not None
        )
        assert await session.scalar(select(AuditLog).where(AuditLog.action == "listing.promoted")) is not None
    removed = await client.delete(f"/api/v1/admin/listings/{listing_id}/promotion", headers=admin_headers)
    assert removed.status_code == 200, removed.text
    assert removed.json()["promoted"] is False


async def grant_viable_admin(user_id: str, email: str) -> None:
    async with SessionLocal() as session:
        user = await session.get(User, UUID(user_id))
        assert user is not None
        user.google_subject = f"google-subject-{user.id}"
        session.add(AdminAccess(email=email.lower(), active=True))
        await session.commit()


async def test_sole_viable_admin_cannot_delete_account(client: AsyncClient, register_user):
    token, admin = await register_user(client, email="sole-admin@example.com", role="host")
    await grant_viable_admin(admin["id"], admin["email"])

    deleted = await client.delete("/api/v1/users/me", headers=auth(token))
    assert deleted.status_code == 409, deleted.text

    async with SessionLocal() as session:
        stored = await session.get(User, UUID(admin["id"]))
        grant = await session.get(AdminAccess, admin["email"].lower())
        assert stored is not None
        assert stored.deleted_at is None
        assert stored.email == admin["email"]
        assert stored.google_subject
        assert grant is not None and grant.active is True


async def test_deleting_one_of_multiple_admins_deactivates_their_grant(client: AsyncClient, register_user):
    first_token, first = await register_user(client, email="first-admin@example.com", role="host")
    second_token, second = await register_user(client, email="second-admin@example.com", role="host")
    await grant_viable_admin(first["id"], first["email"])
    await grant_viable_admin(second["id"], second["email"])

    deleted = await client.delete("/api/v1/users/me", headers=auth(first_token))
    assert deleted.status_code == 204, deleted.text
    assert (await client.get("/api/v1/admin/access", headers=auth(second_token))).status_code == 200

    async with SessionLocal() as session:
        deleted_user = await session.get(User, UUID(first["id"]))
        grant = await session.get(AdminAccess, first["email"].lower())
        assert deleted_user is not None and deleted_user.deleted_at is not None
        assert grant is not None and grant.active is False


async def test_concurrent_admin_self_deletion_preserves_one_viable_admin(client: AsyncClient, register_user):
    first_token, first = await register_user(client, email="concurrent-first@example.com", role="host")
    second_token, second = await register_user(client, email="concurrent-second@example.com", role="host")
    await grant_viable_admin(first["id"], first["email"])
    await grant_viable_admin(second["id"], second["email"])

    first_result, second_result = await asyncio.gather(
        client.delete("/api/v1/users/me", headers=auth(first_token)),
        client.delete("/api/v1/users/me", headers=auth(second_token)),
    )
    assert sorted([first_result.status_code, second_result.status_code]) == [204, 409]

    async with SessionLocal() as session:
        viable = (
            await session.scalars(
                select(User)
                .join(AdminAccess, func.lower(User.email) == AdminAccess.email)
                .where(
                    AdminAccess.active.is_(True),
                    User.deleted_at.is_(None),
                    User.blocked.is_(False),
                    User.google_subject.is_not(None),
                )
            )
        ).all()
        assert len(viable) == 1
