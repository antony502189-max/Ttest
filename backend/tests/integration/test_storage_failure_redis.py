from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from redis.asyncio import from_url
from sqlalchemy import select

from app.core.config import get_settings
from app.core.storage_failure_buffer import FAILED_STORAGE_DELETIONS_KEY, record_failed_storage_deletion
from app.db.session import SessionLocal
from app.models.storage_deletion import StorageDeletionJob
from app.services.storage_deletions import drain_failed_storage_deletion_buffer

pytestmark = pytest.mark.integration


async def test_real_redis_failure_buffer_hands_off_to_postgresql() -> None:
    settings = get_settings()
    assert settings.redis_url
    storage_key = f"external/redis-handoff-{uuid4().hex}.webp"
    redis = from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.srem(FAILED_STORAGE_DELETIONS_KEY, storage_key)
        assert await asyncio.to_thread(record_failed_storage_deletion, storage_key)
        assert await redis.sismember(FAILED_STORAGE_DELETIONS_KEY, storage_key)

        async with SessionLocal() as session:
            assert await drain_failed_storage_deletion_buffer(session) >= 1

        assert not await redis.sismember(FAILED_STORAGE_DELETIONS_KEY, storage_key)
        async with SessionLocal() as session:
            job = await session.scalar(
                select(StorageDeletionJob).where(StorageDeletionJob.storage_key == storage_key)
            )
            assert job is not None
            assert job.attempts == 0
    finally:
        await redis.srem(FAILED_STORAGE_DELETIONS_KEY, storage_key)
        await redis.aclose()
