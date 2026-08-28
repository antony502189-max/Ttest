from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from PIL import Image
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import Listing, User
from app.schemas.listings import ListingWrite
from app.services import listing_limits, listings

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
        lambda: type("Limits", (), {"max_active_listings_per_user": 1, "max_listing_creations_per_day": 10})(),
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
    payload = customer_listing(contactName="Nuevo nombre público")

    first, replay = await asyncio.gather(
        client.post("/api/v1/listings", headers=publication_headers(token, key), json=payload),
        client.post("/api/v1/listings", headers=publication_headers(token, key), json=payload),
    )
    assert first.status_code == replay.status_code == 201
    assert first.json()["id"] == replay.json()["id"] == str(key)

    changed = await client.post(
        "/api/v1/listings",
        headers=publication_headers(token, key),
        json=customer_listing(
            contactName=payload["contactName"],
            contactPhone="+34 600 999 999",
        ),
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
    async with SessionLocal() as session:
        user = await session.get(User, UUID(user_body["id"]))
        assert user is not None
        original_name = user.name
        payload_model = ListingWrite.model_validate(customer_listing(contactName="Must roll back"))

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
        json={"assetIds": [owner_asset.json()["id"]]},
    )
    assert foreign_media.status_code == 422
    assert foreign_media.json()["code"] == "LISTING_IMAGE_INVALID"
