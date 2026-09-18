from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.core.config import Settings
from app.db.session import SessionLocal
from app.main import app
from app.models import AuthSession, User
from app.services import auth

pytestmark = pytest.mark.integration


def session_settings(**overrides) -> Settings:
    values = {
        "jwt_secret": "test-session-secret-with-at-least-32-characters",
        "max_active_sessions_per_user": 2,
        "max_session_issues_per_minute": 100,
        "refresh_token_days": 30,
    }
    values.update(overrides)
    return Settings(**values)


async def create_user(email: str) -> User:
    async with SessionLocal() as session:
        user = User(
            email=email,
            password_hash="unused",
            name="Session Test",
            role="tenant",
            initials="ST",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def test_session_issuance_caps_active_devices_and_removes_expired_rows(monkeypatch):
    settings = session_settings()
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    user = await create_user("session-cap@example.test")

    async with SessionLocal() as session:
        session.add(
            AuthSession(
                user_id=user.id,
                token_hash="e" * 64,
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
            )
        )
        await session.commit()
        stored_user = await session.get(User, user.id)
        assert stored_user is not None
        for index in range(3):
            await auth.issue_session(
                stored_user,
                session,
                user_agent=f"device-{index}",
                client_ip=f"198.51.100.{index + 1}",
            )

    async with SessionLocal() as check:
        total = await check.scalar(
            select(func.count()).select_from(AuthSession).where(AuthSession.user_id == user.id)
        )
        active = await check.scalar(
            select(func.count())
            .select_from(AuthSession)
            .where(
                AuthSession.user_id == user.id,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > datetime.now(UTC),
            )
        )
        expired = await check.scalar(
            select(func.count())
            .select_from(AuthSession)
            .where(
                AuthSession.user_id == user.id,
                AuthSession.expires_at <= datetime.now(UTC),
            )
        )
        assert total == 3
        assert active == 2
        assert expired == 0


async def test_session_issuance_has_an_account_level_rate_limit(monkeypatch):
    settings = session_settings(
        max_active_sessions_per_user=10,
        max_session_issues_per_minute=2,
    )
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    user = await create_user("session-rate@example.test")

    async with SessionLocal() as session:
        stored_user = await session.get(User, user.id)
        assert stored_user is not None
        for index in range(2):
            await auth.issue_session(
                stored_user,
                session,
                user_agent=f"device-{index}",
                client_ip=f"203.0.113.{index + 1}",
            )
        with pytest.raises(HTTPException, match="Too many session rotations") as error:
            await auth.issue_session(
                stored_user,
                session,
                user_agent="abusive-device",
                client_ip="203.0.113.99",
            )
        assert error.value.status_code == 429
        await session.rollback()

    async with SessionLocal() as check:
        total = await check.scalar(
            select(func.count()).select_from(AuthSession).where(AuthSession.user_id == user.id)
        )
        assert total == 2


async def test_logout_revokes_only_the_presented_session_and_keeps_parallel_device_active(
    client: AsyncClient, register_user
):
    _, user = await register_user(client, email="parallel-devices@example.com")
    user_id = UUID(user["id"])
    first_refresh = client.cookies.get("refresh_token")
    assert first_refresh

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Origin": "http://testserver"},
    ) as second_device:
        logged_in = await second_device.post(
            "/api/v1/auth/login",
            json={"email": "parallel-devices@example.com", "password": "Correct-Horse-1234"},
        )
        assert logged_in.status_code == 200, logged_in.text
        second_refresh = second_device.cookies.get("refresh_token")
        assert second_refresh and second_refresh != first_refresh

        logged_out = await client.post("/api/v1/auth/logout")
        assert logged_out.status_code == 204
        assert client.cookies.get("refresh_token") is None
        assert (await client.post("/api/v1/auth/refresh")).status_code == 401

        still_active = await second_device.post("/api/v1/auth/refresh")
        assert still_active.status_code == 200, still_active.text

    async with SessionLocal() as session:
        active = await session.scalar(
            select(func.count())
            .select_from(AuthSession)
            .where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > datetime.now(UTC),
            )
        )
        assert active == 1
