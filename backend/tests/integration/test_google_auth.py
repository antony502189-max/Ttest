from __future__ import annotations

import asyncio
from uuid import UUID

import pytest
from google.auth.exceptions import GoogleAuthError, TransportError
from httpx import AsyncClient

from app.core.config import Settings
from app.db.session import SessionLocal
from app.models import User

pytestmark = pytest.mark.integration


def configure_google_claims(monkeypatch, claims: dict[str, object]) -> None:
    monkeypatch.setattr("app.services.auth.get_settings", lambda: Settings(google_client_id="test-client-id"))
    monkeypatch.setattr("app.services.auth.google_id_token.verify_oauth2_token", lambda *_args, **_kwargs: claims)


async def google_login(client: AsyncClient) -> dict:
    response = await client.post("/api/v1/auth/google", json={"credential": "credential-for-test-only"})
    assert response.status_code == 200, response.text
    return response.json()


async def test_google_gmail_user_selects_role_once_and_refresh_logout_are_safe(client: AsyncClient, monkeypatch):
    configure_google_claims(
        monkeypatch,
        {"iss": "accounts.google.com", "sub": "google-gmail-subject", "email": "new.user@gmail.com", "email_verified": True, "name": "New User"},
    )

    first = await google_login(client)
    assert first["user"]["role"] == "pending"
    assert first["user"]["email"] == "new.user@gmail.com"

    role = await client.post(
        "/api/v1/auth/google/role",
        headers={"Authorization": f"Bearer {first['accessToken']}"},
        json={"role": "host"},
    )
    assert role.status_code == 200, role.text
    assert role.json()["role"] == "host"

    repeat = await google_login(client)
    assert repeat["user"]["role"] == "host"

    refreshed = await client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["user"]["role"] == "host"

    logged_out = await client.post("/api/v1/auth/logout")
    assert logged_out.status_code == 204, logged_out.text
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_google_workspace_links_an_existing_password_account_only_when_authoritative(client: AsyncClient, register_user, monkeypatch):
    token, original = await register_user(client, email="member@example.edu")
    configure_google_claims(
        monkeypatch,
        {"iss": "https://accounts.google.com", "sub": "workspace-subject", "email": "member@example.edu", "email_verified": True, "hd": "example.edu"},
    )

    linked = await google_login(client)
    assert linked["user"]["id"] == original["id"]
    assert linked["user"]["role"] == "tenant"
    assert token


async def test_google_refuses_unsafe_third_party_email_auto_link(client: AsyncClient, register_user, monkeypatch):
    await register_user(client, email="member@example.net")
    configure_google_claims(
        monkeypatch,
        {"iss": "accounts.google.com", "sub": "third-party-subject", "email": "member@example.net", "email_verified": True},
    )

    response = await client.post("/api/v1/auth/google", json={"credential": "credential-for-test-only"})
    assert response.status_code == 409
    assert "Confirm the existing account" in response.json()["detail"]


async def test_google_rejects_a_different_subject_for_an_already_linked_account(
    client: AsyncClient, register_user, monkeypatch
):
    _, original = await register_user(client, email="linked.user@gmail.com")
    async with SessionLocal() as session:
        user = await session.get(User, UUID(original["id"]))
        assert user is not None
        user.google_subject = "original-google-subject"
        await session.commit()

    configure_google_claims(
        monkeypatch,
        {
            "iss": "accounts.google.com",
            "sub": "different-google-subject",
            "email": "linked.user@gmail.com",
            "email_verified": True,
        },
    )
    response = await client.post("/api/v1/auth/google", json={"credential": "credential-for-test-only"})
    assert response.status_code == 409
    assert response.json()["detail"] == "Google account is already linked"

    async with SessionLocal() as session:
        user = await session.get(User, UUID(original["id"]))
        assert user is not None
        assert user.google_subject == "original-google-subject"


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (GoogleAuthError("wrong issuer"), 401, "Invalid Google credential"),
        (TransportError("google unavailable"), 503, "Google sign-in is temporarily unavailable"),
    ],
)
async def test_google_verification_errors_are_mapped_without_internal_500(
    client: AsyncClient, monkeypatch, error, expected_status, expected_detail
):
    monkeypatch.setattr("app.services.auth.get_settings", lambda: Settings(google_client_id="test-client-id"))

    def fail_verification(*_args, **_kwargs):
        raise error

    monkeypatch.setattr("app.services.auth.verify_google_credential", fail_verification)
    response = await client.post("/api/v1/auth/google", json={"credential": "credential-for-test-only"})
    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail


async def test_google_role_can_only_be_selected_once_under_concurrent_requests(
    client: AsyncClient, monkeypatch
):
    configure_google_claims(
        monkeypatch,
        {
            "iss": "accounts.google.com",
            "sub": "concurrent-role-subject",
            "email": "concurrent.role@gmail.com",
            "email_verified": True,
            "name": "Concurrent Role",
        },
    )
    first = await google_login(client)
    headers = {"Authorization": f"Bearer {first['accessToken']}"}

    host, tenant = await asyncio.gather(
        client.post("/api/v1/auth/google/role", headers=headers, json={"role": "host"}),
        client.post("/api/v1/auth/google/role", headers=headers, json={"role": "tenant"}),
    )
    statuses = sorted((host.status_code, tenant.status_code))
    assert statuses == [200, 409]

    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["role"] in {"host", "tenant"}

    repeat = await client.post(
        "/api/v1/auth/google/role",
        headers=headers,
        json={"role": "host" if me.json()["role"] == "tenant" else "tenant"},
    )
    assert repeat.status_code == 409


@pytest.mark.parametrize(
    "claims",
    [
        {
            "iss": "https://evil.example",
            "sub": "bad-issuer-subject",
            "email": "bad.issuer@gmail.com",
            "email_verified": True,
        },
        {
            "iss": "accounts.google.com",
            "email": "missing.subject@gmail.com",
            "email_verified": True,
        },
        {
            "iss": "accounts.google.com",
            "sub": "unverified-subject",
            "email": "unverified@gmail.com",
            "email_verified": False,
        },
    ],
)
async def test_google_rejects_invalid_identity_claims(client: AsyncClient, monkeypatch, claims):
    configure_google_claims(monkeypatch, claims)
    response = await client.post("/api/v1/auth/google", json={"credential": "credential-for-test-only"})
    assert response.status_code == 401
