from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from PIL import Image
from sqlalchemy import delete, func, select

from app.db.session import SessionLocal
from app.models import Listing, ListingImage, MediaAsset, User
from app.schemas.listings import ListingWrite
from app.services import listing_limits, listings
from app.services.duplicate_cleanup import deduplicate_active_listings

pytestmark = pytest.mark.integration


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def publication_headers(token: str, key: UUID | None = None) -> dict[str, str]:
    return {**auth(token), "Idempotency-Key": str(key or uuid4())}


def customer_listing(**overrides) -> dict:
    today = datetime.now(UTC).date()
    payload = {
        "title": "Habitación privada tranquila en Costa Adeje",
        "city": "Adeje",
        "area": "Costa Adeje",
        "street": "Synthetic test street",
        "postcode": "38660",
        "approximateAddress": "Costa Adeje · ubicación aproximada",
        "rentalMode": "long",
        "monthlyPrice": 650,
        "nightlyPrice": None,
        "weeklyPrice": None,
        "roomType": "Habitación individual",
        "availableFrom": today.isoformat(),
        "availableUntil": (today + timedelta(days=180)).isoformat(),
        "minimumStayMonths": 3,
        "minimumNights": None,
        "depositAmount": 650,
        "billsIncluded": True,
        "billsText": "Gastos incluidos en el precio",
        "bathroom": "Baño compartido",
        "kitchen": "Cocina compartida",
        "furnished": True,
        "roomSizeM2": 14,
        "bedroomCount": 3,
        "currentResidents": 2,
        "roomCapacity": 1,
        "shower": "Ducha compartida",
        "homeSizeM2": 82,
        "bathroomCount": 2,
        "rentalUnit": "room",
        "bedType": "single",
        "bedCount": 1,
        "currentRoomResidents": 0,
        "toilet": "Aseo compartido",
        "householdGender": "mixed",
        "householdHasChildren": False,
        "heatingType": "none",
        "accessible": False,
        "floor": "2",
        "couplesAllowed": False,
        "acceptedTenantTypes": ["man", "woman"],
        "tenantRequirement": "single-person",
        "smokingAllowed": False,
        "petsAllowed": False,
        "childrenAllowed": False,
        "empadronamientoAllowed": True,
        "restrictions": ["No se admiten mascotas", "Solo una persona"],
        "amenities": ["Wi-Fi", "Lavadora", "Escritorio"],
        "latitude": 28.0905,
        "longitude": -16.7358,
        "exactLatitude": 28.091,
        "exactLongitude": -16.735,
        "description": "Habitación luminosa con armario y escritorio en una vivienda compartida tranquila.",
        "homeDescription": "Se respetan los horarios de descanso y los turnos de limpieza.",
        "advertiserType": "Particular",
        "expiresAt": (datetime.now(UTC) + timedelta(days=60)).isoformat(),
        "contactName": "Anfitrión de prueba",
        "contactPhone": "+34 600 111 222",
        "contactWhatsapp": "+34 600 111 223",
        "showPhone": True,
        "showWhatsApp": True,
    }
    payload.update(overrides)
    return payload


def png(index: int) -> bytes:
    output = BytesIO()
    Image.new("RGB", (40, 30), (index * 20 % 255, 80, 120)).save(output, "PNG")
    return output.getvalue()


async def test_publication_returns_stable_auth_validation_and_limit_errors(client, register_user, monkeypatch):
    anonymous = await client.post("/api/v1/listings", json=customer_listing())
    assert anonymous.status_code == 401

    tenant_token, _ = await register_user(client, email="publication-tenant@example.com", role="tenant")
    tenant = await client.post(
        "/api/v1/listings", headers=publication_headers(tenant_token), json=customer_listing()
    )
    assert tenant.status_code == 403
    assert tenant.json()["code"] == "HOST_ACCOUNT_REQUIRED"

    host_token, _ = await register_user(client, email="publication-validation@example.com", role="host")
    invalid = await client.post(
        "/api/v1/listings",
        headers=publication_headers(host_token),
        json=customer_listing(monthlyPrice=None),
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "VALIDATION_ERROR"
    assert "monthlyPrice" in invalid.json()["fieldErrors"]

    monkeypatch.setattr(
        listing_limits,
        "get_settings",
        lambda: type("Limits", (), {"max_active_listings_per_user": 1})(),
    )
    first = await client.post(
        "/api/v1/listings", headers=publication_headers(host_token), json=customer_listing(title="First bounded listing")
    )
    assert first.status_code == 201, first.text
    limited = await client.post(
        "/api/v1/listings", headers=publication_headers(host_token), json=customer_listing(title="Second bounded listing")
    )
    assert limited.status_code == 409
    assert limited.json()["code"] == "ACTIVE_LISTING_LIMIT_REACHED"


async def test_unverified_host_error_contract(client):
    registration = await client.post(
        "/api/v1/auth/register",
        json={
            "name": "Unverified Host",
            "email": "publication-unverified@example.com",
            "password": "Correct-Horse-1234",
            "role": "host",
        },
    )
    token = registration.json()["accessToken"]
    rejected = await client.post(
        "/api/v1/listings", headers=publication_headers(token), json=customer_listing()
    )
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "EMAIL_VERIFICATION_REQUIRED"


async def test_publication_is_idempotent_and_contact_sync_is_atomic(client, register_user, monkeypatch):
    token, user_body = await register_user(client, email="publication-idempotent@example.com", role="host")
    key = uuid4()
    uploaded_ids = []
    for index in range(2):
        uploaded = await client.post(
            "/api/v1/uploads",
            headers=auth(token),
            files={"file": (f"idempotency-{index}.png", png(index + 20), "image/png")},
        )
        assert uploaded.status_code == 201, uploaded.text
        uploaded_ids.append(uploaded.json()["id"])
    payload = customer_listing(contactName="Nuevo nombre público", assetIds=[uploaded_ids[0]])

    first, replay = await asyncio.gather(
        client.post("/api/v1/listings", headers=publication_headers(token, key), json=payload),
        client.post("/api/v1/listings", headers=publication_headers(token, key), json=payload),
    )
    assert first.status_code == replay.status_code == 201
    assert first.json()["id"] == replay.json()["id"] == str(key)
    assert first.json()["imageUrls"]

    changed_images = await client.post(
        "/api/v1/listings",
        headers=publication_headers(token, key),
        json={**payload, "assetIds": [uploaded_ids[1]]},
    )
    assert changed_images.status_code == 409
    assert changed_images.json()["code"] == "IDEMPOTENCY_PAYLOAD_MISMATCH"

    changed = await client.post(
        "/api/v1/listings",
        headers=publication_headers(token, key),
        json={
            **payload,
            "contactPhone": "+34 600 999 999",
        },
    )
    assert changed.status_code == 409
    assert changed.json()["code"] == "IDEMPOTENCY_PAYLOAD_MISMATCH"

    async with SessionLocal() as session:
        assert await session.scalar(select(func.count()).select_from(Listing)) == 1
        user = await session.get(User, UUID(user_body["id"]))
        assert user is not None
        assert user.name == "Nuevo nombre público"
        assert user.phone == "+34 600 111 222"

    token, user_body = await register_user(client, email="publication-rollback@example.com", role="host")
    rollback_assets = await client.seed_listing_assets(user_body["id"], 5)
    async with SessionLocal() as session:
        user = await session.get(User, UUID(user_body["id"]))
        assert user is not None
        original_name = user.name
        payload_model = ListingWrite.model_validate(customer_listing(contactName="Must roll back", assetIds=rollback_assets))

        async def fail_notification(*args, **kwargs):
            raise RuntimeError("synthetic notification failure")

        monkeypatch.setattr(listings, "create_notification", fail_notification)
        with pytest.raises(RuntimeError, match="synthetic notification failure"):
            await listings.create_listing(payload_model, user, session, listing_id=uuid4())
        await session.rollback()

    async with SessionLocal() as session:
        user = await session.get(User, UUID(user_body["id"]))
        assert user is not None and user.name == original_name
        assert (
            await session.scalar(
                select(func.count()).select_from(Listing).where(Listing.owner_user_id == UUID(user_body["id"]))
            )
            == 0
        )


@pytest.mark.parametrize("injected", ["ownerUserId", "status", "promoted", "isExternal", "source"])
async def test_create_rejects_server_owned_fields(client, register_user, injected):
    token, _ = await register_user(client, email=f"publication-injection-{injected.lower()}@example.com", role="host")
    payload = customer_listing()
    payload[injected] = "attacker-controlled"
    response = await client.post(
        "/api/v1/listings", headers=publication_headers(token), json=payload
    )
    assert response.status_code == 422
    assert injected in response.json()["fieldErrors"]


async def test_customer_like_listing_with_eight_images_publishes(client, register_user):
    token, _ = await register_user(client, email="publication-customer-fixture@example.com", role="host")
    created = await client.post(
        "/api/v1/listings", headers=publication_headers(token), json=customer_listing()
    )
    assert created.status_code == 201, created.text
    uploads = []
    for index in range(8):
        uploaded = await client.post(
            "/api/v1/uploads",
            headers=auth(token),
            files={"file": (f"synthetic-{index}.png", png(index), "image/png")},
        )
        assert uploaded.status_code == 201, uploaded.text
        uploads.append(uploaded.json()["id"])
    attached = await client.put(
        f"/api/v1/listings/{created.json()['id']}/images",
        headers=auth(token),
        json={"assetIds": uploads},
    )
    assert attached.status_code == 200, attached.text
    assert len(attached.json()) == 8
    assert attached.json()[0]["isCover"] is True
    assert [item["sortOrder"] for item in attached.json()] == list(range(8))


async def test_listing_and_media_ownership_boundaries(client, register_user):
    owner_token, _ = await register_user(client, email="publication-owner@example.com", role="host")
    attacker_token, _ = await register_user(client, email="publication-attacker@example.com", role="host")
    owner_listing = await client.post(
        "/api/v1/listings", headers=publication_headers(owner_token), json=customer_listing(title="Owner listing")
    )
    attacker_listing = await client.post(
        "/api/v1/listings",
        headers=publication_headers(attacker_token),
        json=customer_listing(
            title="Holiday attacker listing",
            rentalMode="holiday",
            monthlyPrice=None,
            nightlyPrice=75,
            minimumStayMonths=0,
            minimumNights=2,
        ),
    )
    assert owner_listing.status_code == attacker_listing.status_code == 201

    forbidden_update = await client.patch(
        f"/api/v1/listings/{owner_listing.json()['id']}",
        headers=auth(attacker_token),
        json={"title": "Attacker changed this listing"},
    )
    assert forbidden_update.status_code == 403

    owner_asset = await client.post(
        "/api/v1/uploads",
        headers=auth(owner_token),
        files={"file": ("owner.png", png(9), "image/png")},
    )
    foreign_media = await client.put(
        f"/api/v1/listings/{attacker_listing.json()['id']}/images",
        headers=auth(attacker_token),
        json={"assetIds": [owner_asset.json()["id"], *[
            url.rsplit("/", 1)[-1] for url in attacker_listing.json()["imageUrls"][:4]
        ]]},
    )
    assert foreign_media.status_code == 422
    assert foreign_media.json()["code"] == "LISTING_IMAGE_INVALID"


def patterned_png(seed: int) -> bytes:
    output = BytesIO()
    image = Image.new("RGB", (64, 48), (20 + seed % 50, 30, 40))
    for x in range(64):
        for y in range(48):
            if (x * 3 + y * 5 + seed) % 17 < 5:
                image.putpixel((x, y), ((seed * 29 + x * 7) % 255, (y * 11 + seed) % 255, (x + y * 3) % 255))
    image.save(output, "PNG")
    return output.getvalue()


async def upload_gallery(client, token: str, seeds: list[int]) -> list[str]:
    asset_ids = []
    if len(seeds) < 5:
        seeds = [*seeds, *(seeds[0] + 10_000 + index for index in range(5 - len(seeds)))]
    for seed in seeds:
        uploaded = await client.post(
            "/api/v1/uploads",
            headers=auth(token),
            files={"file": (f"gallery-{seed}.png", patterned_png(seed), "image/png")},
        )
        assert uploaded.status_code == 201, uploaded.text
        asset_ids.append(uploaded.json()["id"])
    return asset_ids


async def test_user_upload_persists_visual_fingerprint_for_duplicate_detection(client, register_user):
    token, _ = await register_user(client, email="upload-phash@example.com", role="host")
    uploaded = await client.post(
        "/api/v1/uploads",
        headers=auth(token),
        files={"file": ("visual-fingerprint.png", patterned_png(77), "image/png")},
    )
    assert uploaded.status_code == 201, uploaded.text

    async with SessionLocal() as session:
        asset = await session.get(MediaAsset, UUID(uploaded.json()["id"]))
        assert asset is not None
        assert asset.perceptual_hash is not None
        assert len(asset.perceptual_hash) == 16


async def test_duplicate_gallery_blocks_even_when_address_price_and_text_change(client, register_user):
    first_token, _ = await register_user(client, email="duplicate-first@example.com", role="host")
    second_token, _ = await register_user(client, email="duplicate-second@example.com", role="host")

    first_assets = await upload_gallery(client, first_token, [101, 102, 103])
    second_assets = await upload_gallery(client, second_token, [101, 102, 103])

    first = await client.post(
        "/api/v1/listings",
        headers=publication_headers(first_token),
        json=customer_listing(assetIds=first_assets),
    )
    assert first.status_code == 201, first.text

    duplicate = await client.post(
        "/api/v1/listings",
        headers=publication_headers(second_token),
        json=customer_listing(
            assetIds=second_assets,
            title="Texto completamente distinto",
            description="Otra descripción que no participa en la detección.",
            monthlyPrice=1999,
            street="Otra calle distinta",
            postcode="38001",
            approximateAddress="Otra zona",
            latitude=28.45,
            longitude=-16.21,
            exactLatitude=28.451,
            exactLongitude=-16.211,
        ),
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["code"] == "DUPLICATE_LISTING_IMAGES"
    assert "assetIds" in duplicate.json()["fieldErrors"]

    async with SessionLocal() as session:
        persisted = int(await session.scalar(select(func.count(Listing.id)).where(Listing.deleted_at.is_(None))) or 0)
    assert persisted == 1


async def test_same_owner_duplicate_gallery_is_rejected_without_persisting_second_listing(client, register_user):
    token, user_body = await register_user(client, email="same-owner-duplicate@example.com", role="host")
    first_assets = await upload_gallery(client, token, [111, 112, 113])
    duplicate_assets = await upload_gallery(client, token, [111, 112, 113])

    first = await client.post(
        "/api/v1/listings",
        headers=publication_headers(token),
        json=customer_listing(assetIds=first_assets, title="Первое объявление с этой галереей"),
    )
    assert first.status_code == 201, first.text

    duplicate = await client.post(
        "/api/v1/listings",
        headers=publication_headers(token),
        json=customer_listing(
            assetIds=duplicate_assets,
            title="Повторное объявление с другими данными",
            monthlyPrice=1777,
            street="Completely different street",
            postcode="38002",
        ),
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["code"] == "DUPLICATE_LISTING_IMAGES"
    assert "assetIds" in duplicate.json()["fieldErrors"]

    async with SessionLocal() as session:
        persisted = int(
            await session.scalar(
                select(func.count(Listing.id)).where(
                    Listing.owner_user_id == UUID(user_body["id"]),
                    Listing.deleted_at.is_(None),
                )
            )
            or 0
        )
    assert persisted == 1

    replacement_assets = await upload_gallery(client, token, [121, 122, 123])
    replacement = await client.post(
        "/api/v1/listings",
        headers=publication_headers(token),
        json=customer_listing(
            assetIds=replacement_assets,
            title="Новая галерея после отказа",
            monthlyPrice=1777,
            street="Completely different street",
            postcode="38002",
        ),
    )
    assert replacement.status_code == 201, replacement.text

    async with SessionLocal() as session:
        persisted = int(
            await session.scalar(
                select(func.count(Listing.id)).where(
                    Listing.owner_user_id == UUID(user_body["id"]),
                    Listing.deleted_at.is_(None),
                )
            )
            or 0
        )
    assert persisted == 2


async def test_unreconciled_external_gallery_does_not_block_user_publication(client, register_user):
    first_token, _ = await register_user(client, email="stale-external-a@example.com", role="host")
    second_token, _ = await register_user(client, email="stale-external-b@example.com", role="host")

    first_assets = await upload_gallery(client, first_token, [151, 152, 153])
    second_assets = await upload_gallery(client, second_token, [151, 152, 153])

    first = await client.post(
        "/api/v1/listings",
        headers=publication_headers(first_token),
        json=customer_listing(assetIds=first_assets),
    )
    assert first.status_code == 201, first.text

    async with SessionLocal() as session:
        stale_external = await session.get(Listing, UUID(first.json()["id"]))
        assert stale_external is not None
        stale_external.is_external = True
        stale_external.primary_source = "Idealista"
        stale_external.external_image_urls = [
            f"https://images.example.test/current-{index}.webp"
            for index in range(6)
        ]
        await session.commit()

    allowed = await client.post(
        "/api/v1/listings",
        headers=publication_headers(second_token),
        json=customer_listing(
            assetIds=second_assets,
            title="Habitación legítima frente a snapshot parser no reconciliado",
        ),
    )
    assert allowed.status_code == 201, allowed.text


async def test_same_address_and_price_with_different_gallery_is_allowed(client, register_user):
    first_token, _ = await register_user(client, email="same-address-a@example.com", role="host")
    second_token, _ = await register_user(client, email="same-address-b@example.com", role="host")

    first_assets = await upload_gallery(client, first_token, [201, 202, 203])
    second_assets = await upload_gallery(client, second_token, [301, 302, 303])

    first = await client.post(
        "/api/v1/listings",
        headers=publication_headers(first_token),
        json=customer_listing(assetIds=first_assets),
    )
    second = await client.post(
        "/api/v1/listings",
        headers=publication_headers(second_token),
        json=customer_listing(assetIds=second_assets),
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text


async def test_shared_home_photos_do_not_block_a_different_room_gallery(client, register_user):
    first_token, _ = await register_user(client, email="shared-gallery-a@example.com", role="host")
    second_token, _ = await register_user(client, email="shared-gallery-b@example.com", role="host")
    shared = [401, 402, 403, 404]

    first_assets = await upload_gallery(client, first_token, [*shared, 405])
    second_assets = await upload_gallery(client, second_token, [*shared, 406])

    first = await client.post(
        "/api/v1/listings",
        headers=publication_headers(first_token),
        json=customer_listing(assetIds=first_assets, title="Habitación A"),
    )
    second = await client.post(
        "/api/v1/listings",
        headers=publication_headers(second_token),
        json=customer_listing(assetIds=second_assets, title="Habitación B"),
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text


async def test_replacing_images_cannot_turn_listing_into_duplicate(client, register_user):
    first_token, _ = await register_user(client, email="replace-duplicate-a@example.com", role="host")
    second_token, _ = await register_user(client, email="replace-duplicate-b@example.com", role="host")

    canonical_assets = await upload_gallery(client, first_token, [501, 502, 503])
    initial_assets = await upload_gallery(client, second_token, [601, 602, 603])
    duplicate_assets = await upload_gallery(client, second_token, [501, 502, 503])

    canonical = await client.post(
        "/api/v1/listings",
        headers=publication_headers(first_token),
        json=customer_listing(assetIds=canonical_assets),
    )
    editable = await client.post(
        "/api/v1/listings",
        headers=publication_headers(second_token),
        json=customer_listing(assetIds=initial_assets),
    )
    assert canonical.status_code == editable.status_code == 201

    rejected = await client.put(
        f"/api/v1/listings/{editable.json()['id']}/images",
        headers=auth(second_token),
        json={"assetIds": duplicate_assets},
    )
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "DUPLICATE_LISTING_IMAGES"


async def test_concurrent_duplicate_publications_leave_one_listing(client, register_user):
    first_token, _ = await register_user(client, email="concurrent-duplicate-a@example.com", role="host")
    second_token, _ = await register_user(client, email="concurrent-duplicate-b@example.com", role="host")
    first_assets = await upload_gallery(client, first_token, [701, 702, 703])
    second_assets = await upload_gallery(client, second_token, [701, 702, 703])

    responses = await asyncio.gather(
        client.post(
            "/api/v1/listings",
            headers=publication_headers(first_token),
            json=customer_listing(assetIds=first_assets),
        ),
        client.post(
            "/api/v1/listings",
            headers=publication_headers(second_token),
            json=customer_listing(assetIds=second_assets),
        ),
    )

    assert sorted(response.status_code for response in responses) == [201, 409]
    rejected = next(response for response in responses if response.status_code == 409)
    assert rejected.json()["code"] == "DUPLICATE_LISTING_IMAGES"

    async with SessionLocal() as session:
        persisted = int(await session.scalar(select(func.count(Listing.id)).where(Listing.deleted_at.is_(None))) or 0)
    assert persisted == 1



async def test_existing_duplicate_cleanup_is_dry_run_then_idempotent_apply(client, register_user):
    first_token, _ = await register_user(client, email="cleanup-duplicate-a@example.com", role="host")
    second_token, _ = await register_user(client, email="cleanup-duplicate-b@example.com", role="host")

    canonical_assets = await upload_gallery(client, first_token, [801, 802, 803])
    initial_assets = await upload_gallery(client, second_token, [901, 902, 903])
    duplicate_assets = await upload_gallery(client, second_token, [801, 802, 803])

    first = await client.post(
        "/api/v1/listings",
        headers=publication_headers(first_token),
        json=customer_listing(assetIds=canonical_assets),
    )
    second = await client.post(
        "/api/v1/listings",
        headers=publication_headers(second_token),
        json=customer_listing(assetIds=initial_assets),
    )
    assert first.status_code == second.status_code == 201

    first_id = UUID(first.json()["id"])
    second_id = UUID(second.json()["id"])
    async with SessionLocal() as session:
        await session.execute(delete(ListingImage).where(ListingImage.listing_id == second_id))
        for order, asset_id in enumerate(duplicate_assets):
            session.add(
                ListingImage(
                    listing_id=second_id,
                    media_asset_id=UUID(asset_id),
                    sort_order=order,
                    is_cover=order == 0,
                )
            )
        await session.commit()

        dry_run = await deduplicate_active_listings(session, apply=False)
        assert dry_run["duplicates"] == 1
        assert dry_run["changed"] == 0

        first_listing = await session.get(Listing, first_id)
        second_listing = await session.get(Listing, second_id)
        assert first_listing is not None and first_listing.status != "closed"
        assert second_listing is not None and second_listing.status != "closed"

        applied = await deduplicate_active_listings(session, apply=True)
        assert applied["duplicates"] == 1
        assert applied["changed"] == 1

        await session.refresh(first_listing)
        await session.refresh(second_listing)
        assert first_listing.status != "closed"
        assert second_listing.status == "closed"
        assert second_listing.closed_reason == "duplicate"

        repeated = await deduplicate_active_listings(session, apply=True)
        assert repeated["duplicates"] == 0
        assert repeated["changed"] == 0

    republish = await client.post(
        f"/api/v1/listings/{second_id}/renew",
        headers=auth(second_token),
    )
    assert republish.status_code == 409
    assert republish.json()["code"] == "DUPLICATE_LISTING_IMAGES"
