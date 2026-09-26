from __future__ import annotations

import asyncio
import hashlib
import os
import random
from collections.abc import AsyncIterator
from io import BytesIO
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from PIL import Image
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

from app.db.session import SessionLocal, engine
from app.main import app, rate_limiter
from app.models import MediaAsset, User
from app.storage import get_storage


class ListingFixtureClient(AsyncClient):
    """Give unrelated listing-flow tests valid photos under the owner contract.

    Media boundary tests use a raw client to bypass this unrelated-flow helper.
    Replays with the same publication key reuse their seeded asset IDs.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._listing_assets: dict[tuple[str, str], list[str]] = {}
        self._seed_lock = asyncio.Lock()

    async def seed_listing_assets(self, owner_id: str, count: int) -> list[str]:
        asset_ids: list[str] = []
        async with SessionLocal() as session:
            for _ in range(count):
                storage_key = f"{owner_id}/fixture-{uuid4().hex}.webp"
                output = BytesIO()
                image = Image.new("RGB", (16, 16))
                pixels = random.Random(uuid4().int)
                image.putdata([(pixels.randrange(256), pixels.randrange(256), pixels.randrange(256)) for _ in range(256)])
                image.save(output, format="WEBP")
                content = output.getvalue()
                get_storage().put(storage_key, content)
                asset = MediaAsset(
                    owner_id=UUID(owner_id), storage_key=storage_key, mime_type="image/webp",
                    size_bytes=len(content), width=16, height=16,
                    checksum=hashlib.sha256(content).hexdigest(), kind="listing_image",
                )
                session.add(asset)
                await session.flush()
                asset_ids.append(str(asset.id))
            await session.commit()
        return asset_ids

    async def request(self, method: str, url, **kwargs):
        payload = kwargs.get("json")
        if method.upper() == "POST" and str(url) == "/api/v1/listings" and isinstance(payload, dict) and len(payload.get("assetIds", [])) < 5:
            me = await super().request("GET", "/api/v1/auth/me", headers=kwargs.get("headers"))
            if me.status_code == 200:
                owner_id = me.json()["id"]
                key = (owner_id, (kwargs.get("headers") or {}).get("Idempotency-Key", repr(payload.get("assetIds", uuid4()))))
                async with self._seed_lock:
                    supplemental = self._listing_assets.get(key)
                    if supplemental is None:
                        supplemental = await self.seed_listing_assets(owner_id, 5 - len(payload.get("assetIds", [])))
                        self._listing_assets[key] = supplemental
                kwargs["json"] = {**payload, "assetIds": [*payload.get("assetIds", []), *supplemental]}
        return await super().request(method, url, **kwargs)


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture(autouse=True)
async def clean_database() -> AsyncIterator[None]:
    # Integration clients all share the in-process ASGI app.  Reset its
    # limiter with the database so one test cannot exhaust the registration
    # budget of the next test.  The audit uses Redis DB 15, which is isolated
    # specifically for these tests.
    rate_limiter._memory._attempts.clear()
    if rate_limiter._redis:
        await rate_limiter._redis._client.flushdb()
    async with engine.begin() as connection:
        table_names = (
            (
                await connection.execute(
                    text(
                        "SELECT tablename FROM pg_tables "
                        "WHERE schemaname = 'public' "
                        "AND tablename NOT IN ('alembic_version', 'spatial_ref_sys')"
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
    async with ListingFixtureClient(
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
    # Most integration tests exercise unrelated flows.  They receive a
    # verified fixture account; dedicated verification tests cover the gate.
    async with SessionLocal() as session:
        user = await session.get(User, body["user"]["id"])
        assert user is not None
        user.email_verified = True
        await session.commit()
    return body["accessToken"], body["user"]


@pytest.fixture
def register_user():
    return register
