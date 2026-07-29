from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://ttest:ttest@localhost:5432/ttest_test"),
)
os.environ.setdefault("JWT_SECRET", "integration-test-secret-at-least-32-characters")
os.environ.setdefault("AUTO_PUBLISH_LISTINGS", "true")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("MEDIA_ROOT", "var/test-media")
os.environ.setdefault("FRONTEND_ORIGINS", "http://testserver")

from app.db.session import engine
from app.main import app


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture(autouse=True)
async def clean_database() -> AsyncIterator[None]:
    async with engine.begin() as connection:
        table_names = (
            (
                await connection.execute(
                    text(
                        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
                    )
                )
            )
            .scalars()
            .all()
        )
        if table_names:
            quoted = ", ".join(f'"{name}"' for name in table_names)
            await connection.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))
    yield


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Origin": "http://testserver"},
    ) as value:
        yield value


async def register(client: AsyncClient, *, email: str, role: str = "tenant") -> tuple[str, dict]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"name": email.split("@", 1)[0], "email": email, "password": "Correct-Horse-1234", "role": role},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return body["accessToken"], body["user"]


@pytest.fixture
def register_user():
    return register
