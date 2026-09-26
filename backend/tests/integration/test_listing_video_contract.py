from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.v1 import uploads
from app.db.session import SessionLocal
from app.models import Listing, MediaAsset, User
from app.models.storage_deletion import StorageDeletionJob
from app.repositories.listings import point
from app.services.data_retention import prune_unattached_media
from app.services.listings import _replace_listing_video_locked, delete_listing
from app.services.users import delete_account

pytestmark = pytest.mark.integration


async def video_fixture(owner_id: UUID, *, size: int = 10) -> MediaAsset:
    return MediaAsset(
        owner_id=owner_id, storage_key=f"{owner_id}/{uuid4()}.mp4",
        mime_type="video/mp4", size_bytes=size, width=1280, height=720,
        checksum=uuid4().hex * 2, kind="listing_image",
    )


def listing_fixture(owner_id: UUID) -> Listing:
    return Listing(
        owner_user_id=owner_id, title="Video lifecycle listing", city="Adeje", area="Centro",
        approximate_address="Centro", rental_mode="long", monthly_price=700,
        location=point(-16.73, 28.09), status="draft",
    )


async def test_video_range_responses_use_only_partial_storage_reads(client, register_user, monkeypatch):
    token, owner = await register_user(client, email="video-range@example.com", role="host")
    async with SessionLocal() as session:
        asset = await video_fixture(UUID(owner["id"]))
        session.add(asset)
        await session.commit()
        asset_id = asset.id

    class RangeOnlyStorage:
        def __init__(self):
            self.reads: list[tuple[int, int]] = []

        def get(self, _key):
            raise AssertionError("Full object reads are forbidden for video delivery")

        def get_range(self, _key, start, end):
            self.reads.append((start, end))
            return b"0123456789"[start:end + 1]

    storage = RangeOnlyStorage()
    monkeypatch.setattr(uploads, "get_storage", lambda: storage)
    path = f"/api/v1/media/{asset_id}"
    headers = {"Authorization": f"Bearer {token}"}

    normal = await client.get(path, headers={**headers, "Range": "bytes=2-5"})
    assert normal.status_code == 206 and normal.content == b"2345"
    assert normal.headers["content-range"] == "bytes 2-5/10"
    assert normal.headers["content-length"] == "4"
    suffix = await client.get(path, headers={**headers, "Range": "bytes=-3"})
    assert suffix.status_code == 206 and suffix.content == b"789"
    invalid = await client.get(path, headers={**headers, "Range": "bytes=20-"})
    assert invalid.status_code == 416 and invalid.headers["content-range"] == "bytes */10"
    complete = await client.get(path, headers=headers)
    assert complete.status_code == 200 and complete.content == b"0123456789"
    assert complete.headers["content-length"] == "10"
    assert storage.reads == [(2, 5), (7, 9), (0, 9)]


async def test_video_replacement_reuse_and_listing_deletion_cleanup(client, register_user):
    _token, owner = await register_user(client, email="video-lifecycle@example.com", role="host")
    owner_id = UUID(owner["id"])
    async with SessionLocal() as session:
        user = await session.get(User, owner_id)
        assert user is not None
        first_listing = listing_fixture(owner_id)
        second_listing = listing_fixture(owner_id)
        first_video = await video_fixture(owner_id)
        replacement_video = await video_fixture(owner_id)
        session.add_all([first_listing, second_listing, first_video, replacement_video])
        await session.flush()
        first_id, second_id = first_listing.id, second_listing.id
        first_video_id, replacement_id = first_video.id, replacement_video.id

        await _replace_listing_video_locked(first_listing, first_video_id, user, session, admin=False)
        with pytest.raises(HTTPException) as error:
            await _replace_listing_video_locked(second_listing, first_video_id, user, session, admin=False)
        assert error.value.status_code == 409
        await session.commit()

    async with SessionLocal() as session:
        second_listing = await session.get(Listing, second_id)
        assert second_listing is not None
        second_listing.video_asset_id = first_video_id
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()

    async with SessionLocal() as session:
        user = await session.get(User, owner_id)
        first_listing = await session.get(Listing, first_id)
        first_video = await session.get(MediaAsset, first_video_id)
        replacement_video = await session.get(MediaAsset, replacement_id)
        assert user and first_listing and first_video and replacement_video
        await _replace_listing_video_locked(first_listing, first_video_id, user, session, admin=False)
        await _replace_listing_video_locked(first_listing, replacement_id, user, session, admin=False)
        await session.commit()
        assert first_video.deleted_at is not None

        await delete_listing(first_id, user, session)

    async with SessionLocal() as session:
        assert await session.get(MediaAsset, replacement_id) is None
        assert await session.scalar(select(StorageDeletionJob.id).where(StorageDeletionJob.storage_key == replacement_video.storage_key))
        assert await session.get(Listing, second_id) is not None


async def test_account_deletion_and_orphan_sweep_include_video(client, register_user):
    _token, owner = await register_user(client, email="video-account-delete@example.com", role="host")
    owner_id = UUID(owner["id"])
    async with SessionLocal() as session:
        user = await session.get(User, owner_id)
        assert user is not None
        listing = listing_fixture(owner_id)
        attached = await video_fixture(owner_id)
        abandoned = await video_fixture(owner_id)
        abandoned.created_at = datetime.now(UTC) - timedelta(hours=25)
        session.add_all([listing, attached, abandoned])
        await session.flush()
        await _replace_listing_video_locked(listing, attached.id, user, session, admin=False)
        await session.commit()
        listing_id, attached_id, abandoned_id = listing.id, attached.id, abandoned.id

    async with SessionLocal() as session:
        assert await prune_unattached_media(session, now=datetime.now(UTC), batch_size=10) == 1
        await session.commit()
        user = await session.get(User, owner_id)
        assert user is not None
        await delete_account(user, session)

    async with SessionLocal() as session:
        attached = await session.get(MediaAsset, attached_id)
        abandoned = await session.get(MediaAsset, abandoned_id)
        listing = await session.get(Listing, listing_id)
        assert attached and attached.deleted_at is not None
        assert abandoned and abandoned.deleted_at is not None
        assert listing and listing.deleted_at is not None
        keys = set((await session.scalars(select(StorageDeletionJob.storage_key))).all())
        assert {attached.storage_key, abandoned.storage_key} <= keys
