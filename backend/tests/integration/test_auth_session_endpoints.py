from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.core.security import token_hash
from app.db.session import SessionLocal
from app.main import app
from app.models import AuthSession

pytestmark = pytest.mark.integration


async def active_session_count(user_id: UUID) -> int:
    async with SessionLocal() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(AuthSession)
            .where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > datetime.now(UTC),
            )
        )
        return int(count or 0)


async def test_parallel_sessions_survive_logout_of_another_device(client: AsyncClient, register_user):
    _, user = await register_user(client, email="parallel-sessions@example.com")
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
            json={"email": "parallel-sessions@example.com", "password": "Correct-Horse-1234"},
        )
        assert login.status_code == 200, login.text
        second_refresh = second_client.cookies.get("refresh_token")
        assert second_refresh and second_refresh != first_refresh
        assert await active_session_count(user_id) == 2

        logout = await client.post("/api/v1/auth/logout")
        assert logout.status_code == 204, logout.text
        assert (await client.post("/api/v1/auth/refresh")).status_code == 401

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
            headers={"Origin": "http://testserver"},
            cookies={"refresh_token": first_refresh},
        ) as replay_client:
            replay = await replay_client.post("/api/v1/auth/refresh")
        assert replay.status_code == 401
        assert replay.json()["detail"] == "Invalid refresh token"

        async with SessionLocal() as session:
            revoked = await session.scalar(
                select(AuthSession).where(AuthSession.token_hash == token_hash(first_refresh))
            )
            assert revoked is not None
            assert revoked.revoked_at is not None

        surviving = await second_client.post("/api/v1/auth/refresh")
        assert surviving.status_code == 200, surviving.text
        rotated_second = second_client.cookies.get("refresh_token")
        assert rotated_second and rotated_second != second_refresh
        assert surviving.json()["user"]["id"] == str(user_id)
        assert await active_session_count(user_id) == 1


async def test_refresh_requires_cookie(client: AsyncClient):
    client.cookies.clear()
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
    assert response.json()["detail"] == "Refresh token required"
