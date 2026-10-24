import asyncio
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import MediaAsset, Notification, User
from app.models.commercial_advertisement import CommercialAdvertisement
from app.models.moderation import AdminAccess
from app.services.commercial_advertisements import normalize_destination

pytestmark = pytest.mark.integration


def image_file(seed: str = "default") -> bytes:
    output = BytesIO()
    color = tuple(sha256(seed.encode()).digest()[:3])
    Image.new("RGB", (100, 60), color).save(output, format="PNG")
    return output.getvalue()


async def create_ad(client, register_user, email="advertiser@example.com"):
    token, user = await register_user(client, email=email)
    headers = {"Authorization": f"Bearer {token}"}
    upload = await client.post("/api/v1/advertisements/uploads", headers=headers,
                               files={"file": ("banner.png", image_file(email), "image/png")})
    assert upload.status_code == 201, upload.text
    payload = {
        "title": "Helpful local service", "description": "Friendly service for the local community.",
        "imageAssetId": upload.json()["id"], "destinationType": "website",
        "destination": "https://example.org/offer", "packageId": "homepage_1d",
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


async def test_duplicate_banner_reupload_is_rejected_across_accounts(client, register_user):
    ad, payload, headers, _ = await create_ad(client, register_user)
    # Editing the original campaign is allowed.
    assert (await client.patch(f"/api/v1/advertisements/{ad['id']}", headers=headers, json=payload)).status_code == 200
    token, _ = await register_user(client, email="copy-ad@example.com")
    other_headers = {"Authorization": f"Bearer {token}"}
    uploaded = await client.post("/api/v1/advertisements/uploads", headers=other_headers,
                                files={"file": ("renamed.png", image_file("advertiser@example.com"), "image/png")})
    assert uploaded.status_code == 201
    duplicate = await client.post("/api/v1/advertisements", headers=other_headers, json={
        **payload, "imageAssetId": uploaded.json()["id"], "title": "Different title",
        "destination": "https://example.org/different",
    })
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["code"] == "DUPLICATE_ADVERTISEMENT_IMAGE"
    assert "imageAssetId" in duplicate.json()["fieldErrors"]


async def test_edit_cannot_replace_banner_with_an_existing_creative(client, register_user):
    _, original, _, _ = await create_ad(client, register_user, email="first-creative@example.com")
    second, payload, headers, _ = await create_ad(client, register_user, email="second-creative@example.com")
    uploaded = await client.post("/api/v1/advertisements/uploads", headers=headers,
                                files={"file": ("copy.png", image_file("first-creative@example.com"), "image/png")})
    assert uploaded.status_code == 201
    rejected = await client.patch(f"/api/v1/advertisements/{second['id']}", headers=headers,
                                  json={**payload, "imageAssetId": uploaded.json()["id"]})
    assert rejected.status_code == 409, rejected.text
    unchanged = await client.get(f"/api/v1/advertisements/{second['id']}", headers=headers)
    assert unchanged.json()["imageAssetId"] == payload["imageAssetId"]
    assert original["imageAssetId"] != payload["imageAssetId"]


async def test_cancelled_banner_releases_its_photo_identity(client, register_user):
    ad, payload, headers, _ = await create_ad(client, register_user)
    assert (await client.delete(f"/api/v1/advertisements/{ad['id']}", headers=headers)).status_code == 204
    recreated = await client.post("/api/v1/advertisements", headers=headers, json=payload)
    assert recreated.status_code == 201, recreated.text


async def test_concurrent_identical_banner_submissions_leave_one_campaign(client, register_user):
    token, _ = await register_user(client, email="race-duplicate@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    uploaded = await client.post("/api/v1/advertisements/uploads", headers=headers,
                                files={"file": ("race.png", image_file(), "image/png")})
    assert uploaded.status_code == 201
    payload = {"title": "Concurrent campaign", "description": "Duplicate image race regression.",
               "imageAssetId": uploaded.json()["id"], "destinationType": "website",
               "destination": "https://example.org/race", "packageId": "homepage_1d"}
    results = await asyncio.gather(*(client.post("/api/v1/advertisements", headers=headers, json=payload) for _ in range(2)))
    assert sorted(response.status_code for response in results) == [201, 409]
    mine = await client.get("/api/v1/advertisements/mine", headers=headers)
    assert len(mine.json()) == 1


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

    for destination in (
        "http://127.0.0.2/private",
        "http://192.168.1.1/router",
        "http://service.localhost/internal",
        "http://[::1]/",
    ):
        with pytest.raises(ValueError, match="public website"):
            normalize_destination("website", destination)


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
        stored.ends_at = stored.starts_at + timedelta(days=1)
        await session.commit()
    edited = await client.patch(f"/api/v1/advertisements/{ad_id}", headers=owner_headers,
                                json={**payload, "title": "A changed local service"})
    assert edited.status_code == 200 and edited.json()["status"] == "pending_review"
    assert edited.json()["startsAt"] is not None
    assert edited.json()["endsAt"] is not None
    assert (await client.get("/api/v1/advertisements/homepage")).json() == []
    rejected = await client.post(f"/api/v1/admin/advertisements/{ad_id}/reject", headers=admin, json={"note": "Needs changes"})
    assert rejected.status_code == 204
    assert (await client.get("/api/v1/advertisements/homepage")).json() == []
    assert (await client.get("/api/v1/advertisements/mine", headers=owner_headers)).json() == []
    assert (await client.get(f"/api/v1/advertisements/{ad_id}", headers=owner_headers)).status_code == 404
    assert (await client.post(f"/api/v1/admin/advertisements/{ad_id}/reject", headers=admin, json={})).status_code == 404
    resubmitted = await client.patch(f"/api/v1/advertisements/{ad_id}", headers=owner_headers,
                                     json={**payload, "title": "A safer local service"})
    assert resubmitted.status_code == 404
    async with SessionLocal() as session:
        assert await session.get(CommercialAdvertisement, ad_id) is None
        asset = await session.get(MediaAsset, payload["imageAssetId"])
        assert asset.deleted_at is not None
        notifications = (await session.scalars(select(Notification).where(Notification.type == "advertisement_deleted"))).all()
        assert len(notifications) == 1
        assert str(notifications[0].recipient_user_id) == ad["ownerUserId"]
        assert "Needs changes" in notifications[0].body


async def test_admin_publishes_without_payment_and_normal_user_cannot(client, register_user):
    from app.models.payment_order import PaymentOrder
    from app.services.homepage_purchase import one_month_after

    ad, payload, owner_headers, _ = await create_ad(client, register_user)
    denied = await client.post("/api/v1/admin/advertisements", headers=owner_headers, json=payload)
    assert denied.status_code == 403
    # Extra client flags cannot waive an ordinary advertiser's payment.
    forged = await client.patch(f"/api/v1/advertisements/{ad['id']}", headers=owner_headers,
                                json={**payload, "paymentStatus": "waived", "status": "active", "complimentary": True})
    assert forged.status_code == 200
    assert forged.json()["status"] == "pending_payment" and forged.json()["paymentStatus"] == "unpaid"
    admin = await admin_headers(client, register_user)
    uploaded = await client.post("/api/v1/advertisements/uploads", headers=admin,
                                files={"file": ("admin.png", image_file("admin-free"), "image/png")})
    assert uploaded.status_code == 201
    response = await client.post("/api/v1/admin/advertisements", headers=admin,
                                 json={**payload, "imageAssetId": uploaded.json()["id"]})
    assert response.status_code == 201, response.text
    free = response.json()
    assert free["status"] == "active" and free["paymentStatus"] == "waived"
    assert datetime.fromisoformat(free["endsAt"]) == one_month_after(datetime.fromisoformat(free["startsAt"]))
    assert free["paymentOrderId"] is None
    public = (await client.get("/api/v1/advertisements/homepage")).json()
    assert [row["id"] for row in public] == [free["id"]]
    assert (await client.get(free["imageUrl"])).status_code == 200
    assert (await client.get("/api/v1/advertisements/availability")).json()["available"] == 6
    assert (await client.post(f"/api/v1/payments/advertisements/{free['id']}/checkout", headers=admin)).status_code == 409
    async with SessionLocal() as session:
        assert list((await session.scalars(select(PaymentOrder))).all()) == []
    edited = await client.patch(f"/api/v1/advertisements/{free['id']}", headers=admin,
                                json={**payload, "imageAssetId": free["imageAssetId"], "title": "Updated free banner"})
    assert edited.status_code == 200 and edited.json()["status"] == "pending_review"
    approved = await client.post(f"/api/v1/admin/advertisements/{free['id']}/approve", headers=admin, json={})
    assert approved.status_code == 200, approved.text
    assert approved.json()["endsAt"] == free["endsAt"]


async def test_rejection_keeps_paid_order_for_refund_but_removes_banner(client, register_user):
    from app.models.payment_order import PaymentOrder

    ad, _, owner_headers, _ = await create_ad(client, register_user)
    admin = await admin_headers(client, register_user)
    async with SessionLocal() as session:
        stored = await session.get(CommercialAdvertisement, ad["id"])
        order = PaymentOrder(owner_user_id=stored.owner_user_id, kind="advertisement", target_id=stored.id,
                             days=30, duration_months=1, amount_cents=3000, status="paid",
                             paid_at=datetime.now(UTC), fulfillment_status="fulfilled", financial_status="normal")
        session.add(order)
        await session.flush()
        stored.current_payment_order_id = order.id
        stored.status, stored.payment_status = "pending_review", "paid"
        order_id = order.id
        await session.commit()
    assert (await client.get("/api/v1/advertisements/availability")).json()["available"] == 6
    response = await client.post(f"/api/v1/admin/advertisements/{ad['id']}/reject", headers=admin, json={"note": "Not suitable"})
    assert response.status_code == 204, response.text
    assert (await client.get("/api/v1/advertisements/availability")).json()["available"] == 7
    assert (await client.get("/api/v1/advertisements/mine", headers=owner_headers)).json() == []
    async with SessionLocal() as session:
        assert await session.get(CommercialAdvertisement, ad["id"]) is None
        order = await session.get(PaymentOrder, order_id)
        assert order.status == "paid" and order.fulfillment_status == "review_required"
    reviews = (await client.get("/api/v1/payments/admin/review-required", headers=admin)).json()
    assert any(row["id"] == str(order_id) for row in reviews)


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
    renewed = await client.patch(
        f"/api/v1/advertisements/{ad_id}",
        headers=owner_headers,
        json=payload,
    )
    assert renewed.status_code == 200
    assert renewed.json()["status"] == "pending_payment"
    assert renewed.json()["paymentStatus"] == "unpaid"
    assert (await client.get("/api/v1/advertisements/homepage")).json() == []


async def test_blocked_owner_campaign_cannot_be_approved(client, register_user):
    ad, _, owner_headers, owner = await create_ad(client, register_user, email="blocked-ad-owner@example.com")
    assert (
        await client.post(
            f"/api/v1/advertisements/{ad['id']}/fake-payment/complete",
            headers=owner_headers,
        )
    ).status_code == 200
    admin = await admin_headers(client, register_user)
    async with SessionLocal() as session:
        account = await session.get(User, owner["id"])
        assert account is not None
        account.blocked = True
        await session.commit()

    blocked = await client.post(
        f"/api/v1/admin/advertisements/{ad['id']}/approve",
        headers=admin,
        json={},
    )
    assert blocked.status_code == 409
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
        "packageId": "homepage_1d",
    }
    phone = await client.post("/api/v1/advertisements", headers=headers, json={
        **base, "destinationType": "phone", "destination": "612 345 678",
    })
    assert phone.status_code == 201, phone.text
    assert phone.json()["destination"] == "+34612345678"

    # Distinct campaigns need distinct creatives; contact normalization is
    # independent from the duplicate-image guard.
    other_image = await client.post("/api/v1/advertisements/uploads", headers=headers,
                                   files={"file": ("whatsapp.png", image_file("whatsapp"), "image/png")})
    assert other_image.status_code == 201

    whatsapp = await client.post("/api/v1/advertisements", headers=headers, json={
        **base, "imageAssetId": other_image.json()["id"],
        "title": "Servicio WhatsApp", "destinationType": "whatsapp", "destination": "0034 712 345 678",
    })
    assert whatsapp.status_code == 201, whatsapp.text
    assert whatsapp.json()["destination"] == "+34712345678"

    invalid = await client.post("/api/v1/advertisements", headers=headers, json={
        **base, "title": "Número ambiguo", "destinationType": "phone", "destination": "12345678",
    })
    assert invalid.status_code == 422


async def test_homepage_returns_seven_and_rejects_eighth_overlapping_campaign(client, register_user):
    ad, payload, owner_headers, user = await create_ad(client, register_user, email="capacity-owner@example.com")
    ad_id = ad["id"]
    assert (await client.post(f"/api/v1/advertisements/{ad_id}/fake-payment/complete", headers=owner_headers)).status_code == 200
    admin = await admin_headers(client, register_user)
    now = datetime.now(UTC)

    async with SessionLocal() as session:
        for index in range(7):
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
    assert len(public.json()) == 7

    blocked = await client.post(f"/api/v1/admin/advertisements/{ad_id}/approve", headers=admin, json={})
    assert blocked.status_code == 409
    free_blocked = await client.post("/api/v1/admin/advertisements", headers=admin, json=payload)
    assert free_blocked.status_code == 409

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
    assert len((await client.get("/api/v1/advertisements/homepage")).json()) == 7


async def test_concurrent_approvals_cannot_overbook_seven_homepage_slots(client, register_user):
    first, first_payload, first_headers, user = await create_ad(
        client, register_user, email="capacity-race-one@example.com"
    )
    second, _, second_headers, _ = await create_ad(
        client, register_user, email="capacity-race-two@example.com"
    )
    assert (
        await client.post(
            f"/api/v1/advertisements/{first['id']}/fake-payment/complete",
            headers=first_headers,
        )
    ).status_code == 200
    assert (
        await client.post(
            f"/api/v1/advertisements/{second['id']}/fake-payment/complete",
            headers=second_headers,
        )
    ).status_code == 200
    admin = await admin_headers(client, register_user)
    now = datetime.now(UTC)

    async with SessionLocal() as session:
        for index in range(5):
            session.add(
                CommercialAdvertisement(
                    owner_user_id=user["id"],
                    image_asset_id=first_payload["imageAssetId"],
                    title=f"Race capacity ad {index}",
                    description="Concurrent capacity test advertisement for the homepage carousel.",
                    destination_type="website",
                    destination=f"https://example.org/race-{index}",
                    status="active",
                    payment_status="paid",
                    placement="homepage_bottom",
                    package_id="test_homepage_30d",
                    admin_priority=index,
                    starts_at=now - timedelta(hours=1),
                    ends_at=now + timedelta(days=2),
                    approved_at=now - timedelta(hours=1),
                )
            )
        await session.commit()

    responses = await asyncio.gather(
        client.post(f"/api/v1/admin/advertisements/{first['id']}/approve", headers=admin, json={}),
        client.post(f"/api/v1/admin/advertisements/{second['id']}/approve", headers=admin, json={}),
    )
    assert sorted(response.status_code for response in responses) == [200, 200]
    public = await client.get("/api/v1/advertisements/homepage")
    assert public.status_code == 200
    assert len(public.json()) == 7


async def test_active_edit_preserves_paid_window_when_reapproved(client, register_user):
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
    assert edited.json()["startsAt"] is not None
    assert edited.json()["endsAt"] is not None

    reapproved = await client.post(f"/api/v1/admin/advertisements/{ad_id}/approve", headers=admin, json={})
    assert reapproved.status_code == 200, reapproved.text
    assert reapproved.json()["status"] == "active"
    assert reapproved.json()["startsAt"] is not None
    assert reapproved.json()["endsAt"] is not None


async def test_premium_test_payment_and_concurrent_approval_use_one_month(client, register_user):
    from app.services.homepage_purchase import one_month_after
    ad, payload, owner, _ = await create_ad(client, register_user)
    changed = await client.patch(f"/api/v1/advertisements/{ad['id']}", headers=owner,
                                 json={**payload, 'packageId': 'homepage_premium_1m'})
    assert changed.status_code == 200
    assert (await client.post(f"/api/v1/advertisements/{ad['id']}/fake-payment/complete", headers=owner)).status_code == 200
    admin = await admin_headers(client, register_user)
    approvals = await asyncio.gather(*(client.post(f"/api/v1/admin/advertisements/{ad['id']}/approve", headers=admin, json={}) for _ in range(2)))
    assert sorted(r.status_code for r in approvals) == [200, 409]
    result = next(r.json() for r in approvals if r.status_code == 200)
    assert datetime.fromisoformat(result['endsAt']) == one_month_after(datetime.fromisoformat(result['startsAt']))
