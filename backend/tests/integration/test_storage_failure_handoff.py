from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.storage_deletion import StorageDeletionJob
from app.services import storage_deletions

pytestmark = pytest.mark.integration


async def test_redis_failure_buffer_is_committed_before_ack(monkeypatch):
    acknowledged: list[list[str]] = []

    async def read(limit: int) -> list[str]:
        assert limit == 50
        return ["external/buffered.webp", "external/buffered.webp"]

    async def acknowledge(keys: list[str]) -> None:
        async with SessionLocal() as check:
            job = await check.scalar(
                select(StorageDeletionJob).where(StorageDeletionJob.storage_key == "external/buffered.webp")
            )
            assert job is not None
        acknowledged.append(keys)

    monkeypatch.setattr(storage_deletions, "read_failed_storage_deletions", read)
    monkeypatch.setattr(storage_deletions, "acknowledge_failed_storage_deletions", acknowledge)

    async with SessionLocal() as session:
        assert await storage_deletions.drain_failed_storage_deletion_buffer(session) == 2

    assert acknowledged == [["external/buffered.webp", "external/buffered.webp"]]
    async with SessionLocal() as check:
        jobs = (
            await check.scalars(
                select(StorageDeletionJob).where(StorageDeletionJob.storage_key == "external/buffered.webp")
            )
        ).all()
        assert len(jobs) == 1
