from datetime import UTC, datetime
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.security import token_hash
from app.db.session import SessionLocal
from app.models import AuthSession, User
from app.models.moderation import UserRestriction

pytestmark = pytest.mark.integration


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def auth_session_count(user_id: UUID) -> int:
    async with SessionLocal() as session:
        count = await session.scalar(
            select(func.count()).select_from(AuthSession).where(AuthSession.user_id == user_id)
        )
        return int(count or 0)


async def test_register_preserves_password_and_normalizes_identity_fields(client: AsyncClient):
    password = "  Correct-Horse-1234  "
    registered = await client.post(
        "/api/v1/auth/register",
        json={
            "name": "  Alice Example  ",
            "email": "  Alice.Mixed@EXAMPLE.COM  ",
            "password": password,
            "role": " tenant ",
        },
    )
    assert registered.status_code == 201, registered.text
    body = registered.json()
    assert body["user"]["name"] == "Alice Example"
    assert body["user"]["email"] == "alice.mixed@example.com"
    assert body["user"]["role"] == "tenant"

    refresh_token = client.cookies.get("refresh_token")
    assert refresh_token
    set_cookie = registered.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "Path=/api/v1/auth" in set_cookie
    assert "SameSite=lax" in set_cookie

    user_id = UUID(body["user"]["id"])
    async with SessionLocal() as session:
        stored_user = await session.get(User, user_id)
        assert stored_user is not None
        assert stored_user.name == "Alice Example"
        assert stored_user.email == "alice.mixed@example.com"
        stored_session = await session.scalar(
            select(AuthSession).where(AuthSession.user_id == user_id)
        )
        assert stored_session is not None
        assert stored_session.token_hash == token_hash(refresh_token)
        assert stored_session.token_hash != refresh_token

    exact_login = await client.post(
        "/api/v1/auth/login",
        json={"email": " ALICE.MIXED@example.com ", "password": password},
    )
    assert exact_login.status_code == 200, exact_login.text
    assert exact_login.json()["user"]["id"] == str(user_id)
    login_refresh_token = client.cookies.get("refresh_token")
    assert login_refresh_token and login_refresh_token != refresh_token
    assert await auth_session_count(user_id) == 2
    async with SessionLocal() as session:
        issued_login_session = await session.scalar(
            select(AuthSession).where(AuthSession.token_hash == token_hash(login_refresh_token))
        )
        assert issued_login_session is not None
        assert issued_login_session.user_id == user_id

    trimmed_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "alice.mixed@example.com", "password": password.strip()},
    )
    assert trimmed_login.status_code == 401
    assert trimmed_login.json()["detail"] == "Invalid credentials"
    assert await auth_session_count(user_id) == 2


async def test_duplicate_registration_is_case_insensitive_and_does_not_issue_session(client: AsyncClient):
    first = await client.post(
        "/api/v1/auth/register",
        json={
            "name": "Duplicate One",
            "email": "Duplicate@Example.COM",
            "password": "Correct-Horse-1234",
            "role": "tenant",
        },
    )
    assert first.status_code == 201, first.text
    user_id = UUID(first.json()["user"]["id"])
    sessions_before = await auth_session_count(user_id)

    duplicate = await client.post(
        "/api/v1/auth/register",
        json={
            "name": "Duplicate Two",
            "email": "  DUPLICATE@example.com  ",
            "password": "Another-Correct-1234",
            "role": "host",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Email already registered"

    async with SessionLocal() as session:
        users = await session.scalar(
            select(func.count()).select_from(User).where(func.lower(User.email) == "duplicate@example.com")
        )
        assert users == 1
    assert await auth_session_count(user_id) == sessions_before


async def test_wrong_password_blocked_and_deleted_accounts_never_issue_login_session(client: AsyncClient):
    cases = (
        ("wrong-password@example.com", "wrong_password"),
        ("blocked@example.com", "blocked"),
        ("deleted@example.com", "deleted"),
    )
    users: dict[str, UUID] = {}

    for email, _ in cases:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "name": "Local Auth",
                "email": email,
                "password": "Correct-Horse-1234",
                "role": "tenant",
            },
        )
        assert response.status_code == 201, response.text
        users[email] = UUID(response.json()["user"]["id"])

    async with SessionLocal() as session:
        blocked = await session.get(User, users["blocked@example.com"])
        deleted = await session.get(User, users["deleted@example.com"])
        assert blocked is not None and deleted is not None
        blocked.blocked = True
        deleted.deleted_at = datetime.now(UTC)
        await session.commit()

    attempts = (
        ("wrong-password@example.com", "Definitely-Wrong-1234"),
        ("blocked@example.com", "Correct-Horse-1234"),
        ("deleted@example.com", "Correct-Horse-1234"),
    )
    before = {email: await auth_session_count(users[email]) for email, _ in attempts}

    for email, password in attempts:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"

    after = {email: await auth_session_count(users[email]) for email, _ in attempts}
    assert after == before


async def test_full_restriction_keeps_identity_login_but_blocks_normal_account_actions(client: AsyncClient):
    registered = await client.post(
        "/api/v1/auth/register",
        json={
            "name": "Restricted User",
            "email": "restricted@example.com",
            "password": "Correct-Horse-1234",
            "role": "tenant",
        },
    )
    assert registered.status_code == 201, registered.text
    user_id = UUID(registered.json()["user"]["id"])
    sessions_before = await auth_session_count(user_id)

    async with SessionLocal() as session:
        session.add(
            UserRestriction(
                user_id=user_id,
                restriction_type="full",
                reason="Integration restriction",
            )
        )
        await session.commit()

    logged_in = await client.post(
        "/api/v1/auth/login",
        json={"email": "restricted@example.com", "password": "Correct-Horse-1234"},
    )
    assert logged_in.status_code == 200, logged_in.text
    token = logged_in.json()["accessToken"]
    assert await auth_session_count(user_id) == sessions_before + 1

    identity = await client.get("/api/v1/auth/me", headers=auth(token))
    assert identity.status_code == 200
    assert identity.json()["id"] == str(user_id)

    restriction = await client.get("/api/v1/users/me/restriction", headers=auth(token))
    assert restriction.status_code == 200
    assert restriction.json()["restrictionType"] == "full"
    assert restriction.json()["reason"] == "Integration restriction"

    denied = await client.patch(
        "/api/v1/users/me",
        headers=auth(token),
        json={"name": "Should Not Change"},
    )
    assert denied.status_code == 403
