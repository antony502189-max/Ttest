from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from botocore.exceptions import EndpointConnectionError
from sqlalchemy import select

from app.api.v1.uploads import delete_upload
from app.db.session import SessionLocal
from app.models import MediaAsset, User
from app.models.storage_deletion import StorageDeletionJob
from app.schemas.auth import AvatarUpdateRequest
from app.services import storage_deletions
from app.services.listings import mark_orphaned_media
from app.services.users import delete_account, update_avatar

pytestmark = pytest.mark.integration


class RecordingStorage:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def delete(self, storage_key: str) -> None:
        self.deleted.append(storage_key)


class FailingStorage:
    def delete(self, storage_key: str) -> None:
        raise EndpointConnectionError(endpoint_url="http://minio:9000")


async def test_enqueue_is_idempotent_and_successful_delete_removes_job(monkeypatch):
    async with SessionLocal() as setup:
        await storage_deletions.enqueue_storage_deletion(setup, "media/example.webp")
        await storage_deletions.enqueue_storage_deletion(setup, "media/example.webp")
        await setup.commit()

    storage = RecordingStorage()
    monkeypatch.setattr(storage_deletions, "get_storage", lambda: storage)
    async with SessionLocal() as worker:
        result = await storage_deletions.process_storage_deletions(worker)

    assert result == {"deleted": 1, "failed": 0}
    assert storage.deleted == ["media/example.webp"]
    async with SessionLocal() as check:
        assert await check.scalar(select(StorageDeletionJob)) is None


async def test_failure_releases_lease_and_schedules_retry(monkeypatch):
    async with SessionLocal() as setup:
        await storage_deletions.enqueue_storage_deletion(setup, "media/unavailable.webp")
        await setup.commit()

    monkeypatch.setattr(storage_deletions, "get_storage", FailingStorage)
    async with SessionLocal() as worker:
        result = await storage_deletions.process_storage_deletions(worker)

    assert result == {"deleted": 0, "failed": 1}
    async with SessionLocal() as check:
        job = await check.scalar(select(StorageDeletionJob))
        assert job is not None
        assert job.attempts == 1
        assert job.lease_token is None
        assert job.lease_expires_at is None
        assert job.next_attempt_at > datetime.now(UTC)
        assert "endpoint" in (job.last_error or "").casefold()


async def test_active_lease_is_not_double_claimed_but_expired_lease_recovers():
    async with SessionLocal() as setup:
        await storage_deletions.enqueue_storage_deletion(setup, "media/leased.webp")
        await setup.commit()

    async with SessionLocal() as first:
        claims = await storage_deletions.claim_storage_deletions(first, batch_size=1)
        assert len(claims) == 1

    async with SessionLocal() as second:
        assert await storage_deletions.claim_storage_deletions(second, batch_size=1) == []
        job = await second.get(StorageDeletionJob, claims[0].id)
        assert job is not None
        job.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        job.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        await second.commit()
        recovered = await storage_deletions.claim_storage_deletions(second, batch_size=1)
        assert len(recovered) == 1
        assert recovered[0].attempts == 2
        assert recovered[0].lease_token != claims[0].lease_token


async def test_media_soft_delete_enqueues_storage_key_in_same_transaction():
    async with SessionLocal() as session:
        user = User(
            email="storage-delete-owner@example.test",
            password_hash=None,
            name="Storage owner",
            role="host",
            initials="SO",
            email_verified=True,
        )
        session.add(user)
        await session.flush()
        asset = MediaAsset(
            owner_id=user.id,
            storage_key="media/direct-delete.webp",
            mime_type="image/webp",
            size_bytes=10,
            width=1,
            height=1,
            checksum="a" * 64,
            kind="listing_image",
        )
        session.add(asset)
        await session.commit()

        await delete_upload(asset.id, user, session)

    async with SessionLocal() as check:
        persisted_asset = await check.get(MediaAsset, asset.id)
        job = await check.scalar(
            select(StorageDeletionJob).where(StorageDeletionJob.storage_key == "media/direct-delete.webp")
        )
        assert persisted_asset is not None and persisted_asset.deleted_at is not None
        assert job is not None


async def test_avatar_replacement_and_account_deletion_enqueue_storage_keys():
    async with SessionLocal() as session:
        user = User(
            email="storage-account@example.test",
            password_hash=None,
            name="Storage account",
            role="host",
            initials="SA",
            email_verified=True,
        )
        session.add(user)
        await session.flush()
        old_avatar = MediaAsset(
            owner_id=user.id,
            storage_key="media/old-avatar.webp",
            mime_type="image/webp",
            size_bytes=10,
            width=1,
            height=1,
            checksum="b" * 64,
            kind="avatar",
        )
        remaining = MediaAsset(
            owner_id=user.id,
            storage_key="media/account-owned.webp",
            mime_type="image/webp",
            size_bytes=10,
            width=1,
            height=1,
            checksum="c" * 64,
            kind="listing_image",
        )
        session.add_all([old_avatar, remaining])
        await session.flush()
        user.avatar_asset_id = old_avatar.id
        await session.commit()

        await update_avatar(AvatarUpdateRequest(assetId=None), user, session)
        await delete_account(user, session)

    async with SessionLocal() as check:
        keys = set((await check.scalars(select(StorageDeletionJob.storage_key))).all())
        assert keys == {"media/old-avatar.webp", "media/account-owned.webp"}


async def test_orphaned_listing_media_is_soft_deleted_and_enqueued():
    async with SessionLocal() as session:
        user = User(
            email="storage-orphan@example.test",
            password_hash=None,
            name="Storage orphan",
            role="host",
            initials="SO",
            email_verified=True,
        )
        session.add(user)
        await session.flush()
        asset = MediaAsset(
            owner_id=user.id,
            storage_key="media/orphan.webp",
            mime_type="image/webp",
            size_bytes=10,
            width=1,
            height=1,
            checksum="d" * 64,
            kind="listing_image",
        )
        session.add(asset)
        await session.flush()

        assert await mark_orphaned_media(session, {asset.id}) == 1
        await session.commit()

    async with SessionLocal() as check:
        persisted_asset = await check.get(MediaAsset, asset.id)
        job = await check.scalar(
            select(StorageDeletionJob).where(StorageDeletionJob.storage_key == "media/orphan.webp")
        )
        assert persisted_asset is not None and persisted_asset.deleted_at is not None
        assert job is not None
