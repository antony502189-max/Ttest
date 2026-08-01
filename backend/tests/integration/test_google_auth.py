from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.config import Settings

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
