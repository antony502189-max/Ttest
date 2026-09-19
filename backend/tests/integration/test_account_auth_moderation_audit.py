from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.core.security import token_hash
from app.db.session import SessionLocal
from app.main import app
from app.models import AuthSession, MediaAsset, Notification, PasswordResetToken, User
from app.models.moderation import AdminAccess, ModerationNotice, UserRestriction
from app.schemas.auth import UserUpdateRequest
from app.services import users as users_service
from app.services.moderation_expiry import process_expired_moderation

pytestmark = pytest.mark.integration


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def listing_payload(title: str) -> dict[str, object]:
    return {
        "title": title,
        "city": "Santa Cruz de Tenerife",
        "area": "Centro",
        "approximateAddress": "Centro",
        "rentalMode": "long",
        "monthlyPrice": 700,
        "roomType": "Habitación individual",
        "latitude": 28.46,
        "longitude": -16.25,
    }


async def make_admin(user_id: str, email: str) -> None:
    async with SessionLocal() as session:
        user = await session.get(User, UUID(user_id))
        assert user is not None
        user.google_subject = f"audit-admin:{user.id}"
        session.add(AdminAccess(email=email.lower(), active=True))
        await session.commit()


async def test_password_reset_is_single_use_preserves_exact_secret_and_revokes_all_sessions(
    client: AsyncClient,
    register_user,
):
    first_access, user = await register_user(client, email="reset-lifecycle@example.com")
    user_id = UUID(user["id"])
    first_refresh = client.cookies.get("refresh_token")
    assert first_refresh

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Origin": "http://testserver"},
    ) as second_client:
        login = await second_client.post(
            "/api/v1/auth/login",
            json={"email": "reset-lifecycle@example.com", "password": "Correct-Horse-1234"},
        )
        assert login.status_code == 200, login.text
        second_access = login.json()["accessToken"]
        second_refresh = second_client.cookies.get("refresh_token")
        assert second_refresh and second_refresh != first_refresh

        requested = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "reset-lifecycle@example.com"},
        )
        assert requested.status_code == 202, requested.text
        reset_token = requested.json().get("resetToken")
        assert reset_token

        new_password = "  New-Correct-Horse-5678  "
        reset = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": reset_token, "password": new_password},
        )
        assert reset.status_code == 204, reset.text

        async with SessionLocal() as session:
            active_sessions = await session.scalar(
                select(func.count())
                .select_from(AuthSession)
                .where(
                    AuthSession.user_id == user_id,
                    AuthSession.revoked_at.is_(None),
                    AuthSession.expires_at > datetime.now(UTC),
                )
            )
            unconsumed_resets = await session.scalar(
                select(func.count())
                .select_from(PasswordResetToken)
                .where(
                    PasswordResetToken.user_id == user_id,
                    PasswordResetToken.consumed_at.is_(None),
                )
            )
        assert active_sessions == 0
        assert unconsumed_resets == 0

        for raw_refresh in (first_refresh, second_refresh):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
                headers={"Origin": "http://testserver"},
                cookies={"refresh_token": raw_refresh},
            ) as replay:
                rejected = await replay.post("/api/v1/auth/refresh")
            assert rejected.status_code == 401

        for stale_access in (first_access, second_access):
            denied = await client.get("/api/v1/users/me", headers=auth(stale_access))
            assert denied.status_code == 401

        reused = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": reset_token, "password": "Another-Correct-Horse-9012"},
        )
        assert reused.status_code == 400

        old_login = await second_client.post(
            "/api/v1/auth/login",
            json={"email": "reset-lifecycle@example.com", "password": "Correct-Horse-1234"},
        )
        assert old_login.status_code == 401

        exact_login = await second_client.post(
            "/api/v1/auth/login",
            json={"email": "reset-lifecycle@example.com", "password": new_password},
        )
        assert exact_login.status_code == 200, exact_login.text
        fresh_access = exact_login.json()["accessToken"]
        assert (await client.get("/api/v1/users/me", headers=auth(fresh_access))).status_code == 200

        trimmed_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "reset-lifecycle@example.com", "password": new_password.strip()},
        )
        assert trimmed_login.status_code == 401


async def test_logout_revokes_bound_access_token(client: AsyncClient, register_user):
    access_token, _ = await register_user(client, email="logout-access@example.com")
    assert (await client.get("/api/v1/users/me", headers=auth(access_token))).status_code == 200

    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 204, logout.text

    revoked_access = await client.get("/api/v1/users/me", headers=auth(access_token))
    assert revoked_access.status_code == 401


async def test_password_reset_rejects_whitespace_policy_bypass_and_expired_token(
    client: AsyncClient,
    register_user,
):
    await register_user(client, email="reset-expiry@example.com")
    requested = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "reset-expiry@example.com"},
    )
    assert requested.status_code == 202, requested.text
    reset_token = requested.json().get("resetToken")
    assert reset_token

    weak = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "password": "            "},
    )
    assert weak.status_code == 422

    async with SessionLocal() as session:
        row = await session.scalar(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash(reset_token)
            )
        )
        assert row is not None
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()

    expired = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "password": "New-Correct-Horse-5678"},
    )
    assert expired.status_code == 400
    assert "invalid or has expired" in expired.json()["detail"]


async def test_profile_patch_is_partial_and_rejects_privilege_fields(
    client: AsyncClient,
    register_user,
):
    token, original = await register_user(client, email="profile-audit@example.com")
    headers = auth(token)

    updated = await client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={
            "name": "  Profile Audit  ",
            "phone": "  +34 600 000 001  ",
            "showPhone": True,
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["name"] == "Profile Audit"
    assert body["phone"] == "+34 600 000 001"
    assert body["showPhone"] is True
    assert body["role"] == original["role"]
    assert body["email"] == original["email"]

    partial = await client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={"about": "  Only this field changes  "},
    )
    assert partial.status_code == 200, partial.text
    assert partial.json()["about"] == "Only this field changes"
    assert partial.json()["phone"] == "+34 600 000 001"

    for escalation in (
        {"role": "admin"},
        {"email": "attacker@example.com"},
        {"blocked": False},
        {"google_subject": "forged"},
    ):
        rejected = await client.patch("/api/v1/users/me", headers=headers, json=escalation)
        assert rejected.status_code == 422

    null_name = await client.patch("/api/v1/users/me", headers=headers, json={"name": None})
    assert null_name.status_code == 422

    before = await client.get("/api/v1/listings/catalog-version")
    assert before.status_code == 200
    empty = await client.patch("/api/v1/users/me", headers=headers, json={})
    assert empty.status_code == 200
    after = await client.get("/api/v1/listings/catalog-version")
    assert after.json()["version"] == before.json()["version"]

    async with SessionLocal() as session:
        stored = await session.get(User, UUID(original["id"]))
        assert stored is not None
        assert stored.role == original["role"]
        assert stored.email == original["email"]
        assert stored.blocked is False


async def test_avatar_rejects_media_owned_by_another_account(client: AsyncClient, register_user):
    first_token, first = await register_user(client, email="avatar-owner-a@example.com")
    _, second = await register_user(client, email="avatar-owner-b@example.com")
    second_id = UUID(second["id"])

    async with SessionLocal() as session:
        foreign_asset = MediaAsset(
            owner_id=second_id,
            storage_key="media/foreign-avatar-audit.webp",
            mime_type="image/webp",
            size_bytes=10,
            width=1,
            height=1,
            checksum="9" * 64,
            kind="avatar",
        )
        session.add(foreign_asset)
        await session.commit()
        await session.refresh(foreign_asset)
        foreign_asset_id = foreign_asset.id

    rejected = await client.put(
        "/api/v1/users/me/avatar",
        headers=auth(first_token),
        json={"assetId": str(foreign_asset_id)},
    )
    assert rejected.status_code == 404

    extra_field = await client.put(
        "/api/v1/users/me/avatar",
        headers=auth(first_token),
        json={"assetId": None, "role": "admin"},
    )
    assert extra_field.status_code == 422

    async with SessionLocal() as session:
        stored_first = await session.get(User, UUID(first["id"]))
        assert stored_first is not None
        assert stored_first.avatar_asset_id is None


async def test_authorization_boundaries_deny_anonymous_foreign_owner_and_legacy_role_escalation(
    client: AsyncClient,
    register_user,
):
    assert (await client.get("/api/v1/users/me")).status_code == 401
    assert (await client.get("/api/v1/favorites")).status_code == 401

    owner_token, _ = await register_user(client, email="owner-boundary@example.com", role="host")
    other_token, other = await register_user(client, email="other-boundary@example.com", role="host")

    created = await client.post(
        "/api/v1/listings",
        headers=auth(owner_token),
        json=listing_payload("Authorization boundary listing"),
    )
    assert created.status_code == 201, created.text
    listing_id = created.json()["id"]

    foreign_patch = await client.patch(
        f"/api/v1/listings/{listing_id}",
        headers=auth(other_token),
        json={"title": "Foreign mutation"},
    )
    assert foreign_patch.status_code == 403
    foreign_delete = await client.delete(
        f"/api/v1/listings/{listing_id}",
        headers=auth(other_token),
    )
    assert foreign_delete.status_code == 403

    async with SessionLocal() as session:
        stored_other = await session.get(User, UUID(other["id"]))
        assert stored_other is not None
        stored_other.role = "admin"
        await session.commit()

    admin_denied = await client.get("/api/v1/admin/stats", headers=auth(other_token))
    assert admin_denied.status_code == 403
    still_foreign = await client.delete(
        f"/api/v1/listings/{listing_id}",
        headers=auth(other_token),
    )
    assert still_foreign.status_code == 403


async def test_concurrent_account_deletion_is_single_effect_and_old_identity_cannot_return(
    client: AsyncClient,
    register_user,
):
    token, user = await register_user(client, email="delete-race@example.com")
    user_id = UUID(user["id"])

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Origin": "http://testserver"},
    ) as first, AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Origin": "http://testserver"},
    ) as second:
        responses = await asyncio.gather(
            first.delete("/api/v1/users/me", headers=auth(token)),
            second.delete("/api/v1/users/me", headers=auth(token)),
        )

    statuses = [response.status_code for response in responses]
    assert statuses.count(204) == 1
    assert all(status in {204, 401, 404} for status in statuses)

    retry = await client.delete("/api/v1/users/me", headers=auth(token))
    assert retry.status_code == 401

    async with SessionLocal() as session:
        stored = await session.get(User, user_id)
        session_count = await session.scalar(
            select(func.count()).select_from(AuthSession).where(AuthSession.user_id == user_id)
        )
    assert stored is not None
    assert stored.deleted_at is not None
    assert stored.blocked is True
    assert stored.email.endswith("@deleted.invalid")
    assert session_count == 0


async def test_profile_write_cannot_resurrect_fields_after_concurrent_deletion(
    register_user,
    monkeypatch,
):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Origin": "http://testserver"},
    ) as setup_client:
        _, user = await register_user(setup_client, email="delete-profile-race@example.com")
    user_id = UUID(user["id"])

    delete_locked_user = asyncio.Event()
    release_delete = asyncio.Event()
    real_admin_lock = users_service.lock_active_admin_access

    async def controlled_admin_lock(session):
        delete_locked_user.set()
        await release_delete.wait()
        return await real_admin_lock(session)

    monkeypatch.setattr(users_service, "lock_active_admin_access", controlled_admin_lock)

    async with SessionLocal() as delete_session, SessionLocal() as profile_session:
        delete_user = await delete_session.get(User, user_id)
        stale_profile_user = await profile_session.get(User, user_id)
        assert delete_user is not None and stale_profile_user is not None

        delete_task = asyncio.create_task(
            users_service.delete_account(delete_user, delete_session),
            name="delete-account",
        )
        await asyncio.wait_for(delete_locked_user.wait(), timeout=5)

        profile_task = asyncio.create_task(
            users_service.update_profile(
                UserUpdateRequest(name="Must Not Survive Delete", phone="+34 999 999 999"),
                stale_profile_user,
                profile_session,
            ),
            name="profile-write",
        )
        await asyncio.sleep(0.05)
        release_delete.set()

        await delete_task
        with pytest.raises(HTTPException) as error:
            await profile_task
        assert error.value.status_code == 404
        await profile_session.rollback()

    async with SessionLocal() as session:
        stored = await session.get(User, user_id)
        assert stored is not None
        assert stored.deleted_at is not None
        assert stored.name == "Deleted user"
        assert stored.phone == ""


async def test_moderation_full_publish_unrestrict_expiry_and_notices(
    client: AsyncClient,
    register_user,
):
    admin_token, admin = await register_user(client, email="moderation-audit-admin@example.com", role="host")
    host_token, host = await register_user(client, email="moderation-audit-host@example.com", role="host")
    await make_admin(admin["id"], admin["email"])
    admin_headers = auth(admin_token)
    host_headers = auth(host_token)

    created = await client.post(
        "/api/v1/listings",
        headers=host_headers,
        json=listing_payload("Existing moderated listing"),
    )
    assert created.status_code == 201, created.text
    listing_id = created.json()["id"]

    publish_restriction = await client.post(
        f"/api/v1/admin/users/{host['id']}/restrictions",
        headers=admin_headers,
        json={
            "restrictionType": "publish",
            "until": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "reason": "Temporary publishing review",
        },
    )
    assert publish_restriction.status_code == 200, publish_restriction.text

    restriction = await client.get("/api/v1/users/me/restriction", headers=host_headers)
    assert restriction.status_code == 200
    assert restriction.json()["restrictionType"] == "publish"

    notices = await client.get("/api/v1/users/me/moderation-notices", headers=host_headers)
    assert notices.status_code == 200
    restriction_notice = next(item for item in notices.json() if item["kind"] == "user_restricted")

    foreign_notice = await client.patch(
        f"/api/v1/users/me/moderation-notices/{restriction_notice['id']}/read",
        headers=admin_headers,
    )
    assert foreign_notice.status_code == 404
    own_notice = await client.patch(
        f"/api/v1/users/me/moderation-notices/{restriction_notice['id']}/read",
        headers=host_headers,
    )
    assert own_notice.status_code == 204

    profile_allowed = await client.patch(
        "/api/v1/users/me",
        headers=host_headers,
        json={"about": "Profile remains manageable under publish restriction"},
    )
    assert profile_allowed.status_code == 200
    assert profile_allowed.json()["about"] == "Profile remains manageable under publish restriction"

    denied_publish = await client.post(
        "/api/v1/listings",
        headers=host_headers,
        json=listing_payload("Must not publish"),
    )
    assert denied_publish.status_code == 403
    assert denied_publish.json()["code"] == "PUBLISHING_RESTRICTED"

    # Current moderation contract hides an owner's existing public entities
    # while any account restriction is active, then restores them on removal.
    hidden = await client.get(f"/api/v1/listings/{listing_id}")
    assert hidden.status_code == 404

    unrestricted = await client.delete(
        f"/api/v1/admin/users/{host['id']}/restrictions/active",
        headers=admin_headers,
    )
    assert unrestricted.status_code == 200, unrestricted.text
    assert (await client.get(f"/api/v1/listings/{listing_id}")).status_code == 200

    full = await client.post(
        f"/api/v1/admin/users/{host['id']}/restrictions",
        headers=admin_headers,
        json={
            "restrictionType": "full",
            "until": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "reason": "Temporary full restriction",
        },
    )
    assert full.status_code == 200, full.text

    identity = await client.get("/api/v1/users/me", headers=host_headers)
    assert identity.status_code == 200
    support = await client.get("/api/v1/users/me/restriction", headers=host_headers)
    assert support.status_code == 200
    assert support.json()["restrictionType"] == "full"

    blocked_action = await client.get("/api/v1/favorites", headers=host_headers)
    assert blocked_action.status_code == 403
    assert blocked_action.json()["code"] == "ACCOUNT_RESTRICTED"

    blocked_delete = await client.delete("/api/v1/users/me", headers=host_headers)
    assert blocked_delete.status_code == 403
    assert blocked_delete.json()["code"] == "ACCOUNT_RESTRICTED"

    async with SessionLocal() as session:
        active = await session.scalar(
            select(UserRestriction)
            .where(
                UserRestriction.user_id == UUID(host["id"]),
                UserRestriction.restriction_type == "full",
                UserRestriction.revoked_at.is_(None),
            )
            .order_by(UserRestriction.starts_at.desc())
        )
        assert active is not None
        active.ends_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()

    # Enforcement uses the time window directly; access is restored even before
    # the expiry-notification worker catches up.
    restored = await client.get("/api/v1/favorites", headers=host_headers)
    assert restored.status_code == 200

    async with SessionLocal() as session:
        result = await process_expired_moderation(session)
    assert result["users"] == 1

    expiry_notices = await client.get("/api/v1/users/me/moderation-notices", headers=host_headers)
    assert any(item["kind"] == "user_restriction_expired" for item in expiry_notices.json())
    async with SessionLocal() as session:
        expiry_notification = await session.scalar(
            select(Notification).where(
                Notification.recipient_user_id == UUID(host["id"]),
                Notification.type == "user_restriction_expired",
            )
        )
        moderation_notice_count = await session.scalar(
            select(func.count())
            .select_from(ModerationNotice)
            .where(ModerationNotice.user_id == UUID(host["id"]))
        )
    assert expiry_notification is not None
    assert int(moderation_notice_count or 0) >= 3
