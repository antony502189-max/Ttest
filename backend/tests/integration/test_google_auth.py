from __future__ import annotations

import asyncio
from uuid import UUID

import pytest
from fastapi import HTTPException, Request
from google.auth.exceptions import TransportError
from httpx import AsyncClient

from app.api.v1.auth import select_google_role
from app.core.config import Settings
from app.db.session import SessionLocal
from app.models import User
from app.schemas.auth import GoogleRoleRequest

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


async def test_google_verifier_transport_failure_returns_503(client: AsyncClient, monkeypatch):
    monkeypatch.setattr("app.services.auth.get_settings", lambda: Settings(google_client_id="test-client-id"))
    monkeypatch.setattr(
        "app.services.auth.google_id_token.verify_oauth2_token",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TransportError("google unavailable")),
    )

    response = await client.post("/api/v1/auth/google", json={"credential": "credential-for-test-only"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Google sign-in is temporarily unavailable"


async def test_google_role_selection_is_atomic_under_concurrency(client: AsyncClient, monkeypatch):
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
    created = await google_login(client)
    user_id = UUID(created["user"]["id"])
    assert created["user"]["role"] == "pending"

    request = Request({"type": "http", "headers": []})
    async with SessionLocal() as first_session, SessionLocal() as second_session:
        first_user = await first_session.get(User, user_id)
        second_user = await second_session.get(User, user_id)
        assert first_user is not None and second_user is not None
        assert first_user.role == second_user.role == "pending"

        first, second = await asyncio.gather(
            select_google_role(
                GoogleRoleRequest(role="host"),
                request,
                first_user,
                first_session,
            ),
            select_google_role(
                GoogleRoleRequest(role="tenant"),
                request,
                second_user,
                second_session,
            ),
            return_exceptions=True,
        )

    results = (first, second)
    successes = [result for result in results if isinstance(result, dict)]
    conflicts = [result for result in results if isinstance(result, HTTPException)]
    assert len(successes) == 1
    assert len(conflicts) == 1
    assert conflicts[0].status_code == 409
    assert successes[0]["role"] in {"host", "tenant"}

    async with SessionLocal() as session:
        stored = await session.get(User, user_id)
        assert stored is not None
        assert stored.role == successes[0]["role"]
