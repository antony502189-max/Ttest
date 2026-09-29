from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import User
from app.models.commercial_advertisement import CommercialAdvertisement
from app.models.moderation import AdminAccess

pytestmark = pytest.mark.integration


def image_file() -> bytes:
    output = BytesIO()
    Image.new("RGB", (100, 60), (193, 80, 130)).save(output, format="PNG")
    return output.getvalue()


async def create_ad(client, register_user, email="advertiser@example.com"):
    token, user = await register_user(client, email=email)
    headers = {"Authorization": f"Bearer {token}"}
    upload = await client.post("/api/v1/advertisements/uploads", headers=headers,
                               files={"file": ("banner.png", image_file(), "image/png")})
    assert upload.status_code == 201, upload.text
    payload = {
        "title": "Helpful local service", "description": "Friendly service for the local community.",
        "imageAssetId": upload.json()["id"], "destinationType": "website",
        "destination": "https://example.org/offer", "packageId": "test_homepage_30d",
    }
    response = await client.post("/api/v1/advertisements", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json(), payload, headers, user


async def admin_headers(client, register_user):
    token, user = await register_user(client, email="ad-admin@example.com")
    async with SessionLocal() as session:
        account = await session.get(User, user["id"])
        assert account is not None
        account.google_subject = "ad-admin-google"
        session.add(AdminAccess(email=account.email, active=True, created_by=None))
        await session.commit()
    return {"Authorization": f"Bearer {token}"}


async def test_create_requires_auth_and_valid_image_and_destination(client, register_user):
    denied = await client.post("/api/v1/advertisements", json={})
    assert denied.status_code == 401
    token, _ = await register_user(client, email="invalid-ad@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    invalid_image = await client.post("/api/v1/advertisements/uploads", headers=headers,
                                      files={"file": ("bad.png", b"not an image", "image/png")})
    assert invalid_image.status_code == 415
    upload = await client.post("/api/v1/advertisements/uploads", headers=headers,
                               files={"file": ("banner.png", image_file(), "image/png")})
    assert upload.status_code == 201
    base = {"title": "Local service", "description": "A helpful local service for everyone.",
            "imageAssetId": upload.json()["id"], "destinationType": "website"}
    for destination in ("javascript:alert(1)", "data:text/html,hi", "https://example.org\\@evil.test"):
        invalid = await client.post("/api/v1/advertisements", headers=headers,
                                    json={**base, "destination": destination})
        assert invalid.status_code == 422, invalid.text


async def test_payment_moderation_public_visibility_and_media(client, register_user):
    ad, payload, owner_headers, _ = await create_ad(client, register_user)
    ad_id = ad["id"]
    assert ad["status"] == "pending_payment"
    assert ad["paymentStatus"] == "unpaid"
    assert (await client.delete(f"/api/v1/uploads/{payload['imageAssetId']}", headers=owner_headers)).status_code == 409
    assert (await client.get("/api/v1/advertisements/homepage")).json() == []
    assert (await client.get(f"/api/v1/media/{payload['imageAssetId']}?variant=card")).status_code == 404
    checkout = await client.post(f"/api/v1/advertisements/{ad_id}/checkout", headers=owner_headers)
    assert checkout.status_code == 200 and checkout.json()["paymentMode"] == "test"
    assert (await client.get("/api/v1/advertisements/homepage")).json() == []
    paid = await client.post(f"/api/v1/advertisements/{ad_id}/fake-payment/complete", headers=owner_headers)
    assert paid.status_code == 200 and paid.json()["status"] == "pending_review"
    assert paid.json()["paymentStatus"] == "paid"
    assert (await client.get("/api/v1/advertisements/homepage")).json() == []
    other_token, _ = await register_user(client, email="not-admin@example.com")
    other_headers = {"Authorization": f"Bearer {other_token}"}
    assert (await client.post(f"/api/v1/admin/advertisements/{ad_id}/approve", headers=other_headers, json={})).status_code == 403
    assert (await client.patch(f"/api/v1/advertisements/{ad_id}", headers=other_headers, json=payload)).status_code == 404
    assert (await client.get(f"/api/v1/advertisements/{ad_id}", headers=owner_headers)).status_code == 200
    admin = await admin_headers(client, register_user)
    approved = await client.post(f"/api/v1/admin/advertisements/{ad_id}/approve", headers=admin, json={})
    assert approved.status_code == 200, approved.text
    public = (await client.get("/api/v1/advertisements/homepage")).json()
    assert len(public) == 1 and public[0]["id"] == ad_id
    assert public[0]["destinationUrl"] == payload["destination"]
    assert "ownerUserId" not in public[0] and "paymentStatus" not in public[0] and "moderationNote" not in public[0]
    assert (await client.get(f"/api/v1/media/{payload['imageAssetId']}?variant=card")).status_code == 200
    async with SessionLocal() as session:
        stored = await session.get(CommercialAdvertisement, ad_id)
        assert stored is not None
        stored.ends_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()
    assert (await client.get("/api/v1/advertisements/homepage")).json() == []
    async with SessionLocal() as session:
        stored = await session.get(CommercialAdvertisement, ad_id)
        assert stored is not None
        stored.ends_at = datetime.now(UTC) + timedelta(days=1)
        await session.commit()
    edited = await client.patch(f"/api/v1/advertisements/{ad_id}", headers=owner_headers,
                                json={**payload, "title": "A changed local service"})
    assert edited.status_code == 200 and edited.json()["status"] == "pending_review"
    assert edited.json()["startsAt"] is None
    assert edited.json()["endsAt"] is None
    assert (await client.get("/api/v1/advertisements/homepage")).json() == []
    rejected = await client.post(f"/api/v1/admin/advertisements/{ad_id}/reject", headers=admin, json={"note": "Needs changes"})
    assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"
    assert (await client.get("/api/v1/advertisements/homepage")).json() == []
    resubmitted = await client.patch(f"/api/v1/advertisements/{ad_id}", headers=owner_headers,
                                     json={**payload, "title": "A safer local service"})
    assert resubmitted.status_code == 200 and resubmitted.json()["status"] == "pending_review"
    assert (await client.post(f"/api/v1/admin/advertisements/{ad_id}/approve", headers=admin, json={})).status_code == 200
    assert len((await client.get("/api/v1/advertisements/homepage")).json()) == 1
    assert (await client.post(f"/api/v1/admin/advertisements/{ad_id}/deactivate", headers=admin)).status_code == 200
    assert (await client.get("/api/v1/advertisements/homepage")).json() == []


async def test_expired_campaign_requires_new_test_checkout(client, register_user):
    ad, payload, owner_headers, _ = await create_ad(client, register_user)
    ad_id = ad["id"]
    admin = await admin_headers(client, register_user)
    assert (await client.post(f"/api/v1/advertisements/{ad_id}/fake-payment/complete", headers=owner_headers)).status_code == 200
    assert (await client.post(f"/api/v1/admin/advertisements/{ad_id}/approve", headers=admin, json={})).status_code == 200
    async with SessionLocal() as session:
        stored = await session.get(CommercialAdvertisement, ad_id)
        assert stored is not None
        stored.ends_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()
    changed = await client.patch(f"/api/v1/advertisements/{ad_id}", headers=owner_headers,
                                 json={**payload, "title": "Renewed local service"})
    assert changed.status_code == 200
    assert changed.json()["status"] == "pending_payment"
    assert changed.json()["paymentStatus"] == "unpaid"
    assert (await client.get("/api/v1/advertisements/homepage")).json() == []


async def test_spanish_phone_and_whatsapp_destinations_are_normalized(client, register_user):
    token, _ = await register_user(client, email="spanish-ad@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    upload = await client.post(
        "/api/v1/advertisements/uploads",
        headers=headers,
        files={"file": ("banner.png", image_file(), "image/png")},
    )
    assert upload.status_code == 201
    base = {
        "title": "Servicio local",
        "description": "Servicio local disponible para toda la comunidad.",
        "imageAssetId": upload.json()["id"],
        "packageId": "test_homepage_30d",
    }
    phone = await client.post("/api/v1/advertisements", headers=headers, json={
        **base, "destinationType": "phone", "destination": "612 345 678",
    })
    assert phone.status_code == 201, phone.text
    assert phone.json()["destination"] == "+34612345678"

    whatsapp = await client.post("/api/v1/advertisements", headers=headers, json={
        **base, "title": "Servicio WhatsApp", "destinationType": "whatsapp", "destination": "0034 712 345 678",
    })
    assert whatsapp.status_code == 201, whatsapp.text
    assert whatsapp.json()["destination"] == "+34712345678"

    invalid = await client.post("/api/v1/advertisements", headers=headers, json={
        **base, "title": "Número ambiguo", "destinationType": "phone", "destination": "12345678",
    })
    assert invalid.status_code == 422


async def test_homepage_returns_twelve_and_rejects_thirteenth_overlapping_campaign(client, register_user):
    ad, payload, owner_headers, user = await create_ad(client, register_user, email="capacity-owner@example.com")
    ad_id = ad["id"]
    assert (await client.post(f"/api/v1/advertisements/{ad_id}/fake-payment/complete", headers=owner_headers)).status_code == 200
    admin = await admin_headers(client, register_user)
    now = datetime.now(UTC)

    async with SessionLocal() as session:
        for index in range(12):
            session.add(CommercialAdvertisement(
                owner_user_id=user["id"],
                image_asset_id=payload["imageAssetId"],
                title=f"Capacity ad {index}",
                description="Capacity test advertisement for the homepage carousel.",
                destination_type="website",
                destination=f"https://example.org/{index}",
                status="active",
                payment_status="paid",
                placement="homepage_bottom",
                package_id="test_homepage_30d",
                admin_priority=index,
                starts_at=now - timedelta(hours=1),
                ends_at=now + timedelta(days=2),
                approved_at=now - timedelta(hours=1),
            ))
        await session.commit()

    public = await client.get("/api/v1/advertisements/homepage")
    assert public.status_code == 200
    assert len(public.json()) == 12

    blocked = await client.post(f"/api/v1/admin/advertisements/{ad_id}/approve", headers=admin, json={})
    assert blocked.status_code == 409

    async with SessionLocal() as session:
        one = await session.scalar(
            select(CommercialAdvertisement)
            .where(CommercialAdvertisement.id != ad_id, CommercialAdvertisement.status == "active")
            .order_by(CommercialAdvertisement.admin_priority)
        )
        assert one is not None
        one.ends_at = now - timedelta(seconds=1)
        await session.commit()

    approved = await client.post(f"/api/v1/admin/advertisements/{ad_id}/approve", headers=admin, json={})
    assert approved.status_code == 200, approved.text
    assert len((await client.get("/api/v1/advertisements/homepage")).json()) == 12


async def test_active_edit_clears_old_window_and_can_be_reapproved(client, register_user):
    ad, payload, owner_headers, _ = await create_ad(client, register_user, email="reapprove-owner@example.com")
    ad_id = ad["id"]
    admin = await admin_headers(client, register_user)
    assert (await client.post(f"/api/v1/advertisements/{ad_id}/fake-payment/complete", headers=owner_headers)).status_code == 200
    approved = await client.post(f"/api/v1/admin/advertisements/{ad_id}/approve", headers=admin, json={})
    assert approved.status_code == 200

    async with SessionLocal() as session:
        stored = await session.get(CommercialAdvertisement, ad_id)
        assert stored is not None
        stored.ends_at = datetime.now(UTC) + timedelta(seconds=1)
        await session.commit()

    edited = await client.patch(
        f"/api/v1/advertisements/{ad_id}",
        headers=owner_headers,
        json={**payload, "title": "Updated active creative"},
    )
    assert edited.status_code == 200
    assert edited.json()["status"] == "pending_review"
    assert edited.json()["startsAt"] is None
    assert edited.json()["endsAt"] is None

    reapproved = await client.post(f"/api/v1/admin/advertisements/{ad_id}/approve", headers=admin, json={})
    assert reapproved.status_code == 200, reapproved.text
    assert reapproved.json()["status"] == "active"
    assert reapproved.json()["startsAt"] is not None
    assert reapproved.json()["endsAt"] is not None
