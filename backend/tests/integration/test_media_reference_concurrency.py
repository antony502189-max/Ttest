from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.v1 import uploads
from app.db.session import SessionLocal
from app.models import Listing, ListingImage, MediaAsset, User
from app.models.storage_deletion import StorageDeletionJob
from app.repositories.listings import point
from app.schemas.auth import AvatarUpdateRequest
from app.schemas.listings import ListingImagesRequest
from app.services import listings, users

pytestmark = pytest.mark.integration


@dataclass(frozen=True)
class MediaFixture:
    user_id: UUID
    first_listing_id: UUID
    second_listing_id: UUID
    asset_id: UUID
    storage_key: str


async def create_fixture(*, attached: bool) -> MediaFixture:
    async with SessionLocal() as session:
        user = User(
            email=f"media-race-{uuid4()}@example.test",
            password_hash="unused",
            name="Media Race",
            role="host",
            initials="MR",
            email_verified=True,
        )
        session.add(user)
        await session.flush()
        listings_to_add = [
            Listing(
                owner_user_id=user.id,
                title=f"Media race listing {index}",
                city="Santa Cruz de Tenerife",
                area="Centro",
                approximate_address="Centro",
                rental_mode="long",
                monthly_price=700,
                location=point(-16.25, 28.46),
                status="published",
            )
            for index in range(2)
        ]
        session.add_all(listings_to_add)
        await session.flush()
        storage_key = f"media/race-{uuid4()}.webp"
        asset = MediaAsset(
            owner_id=user.id,
            storage_key=storage_key,
            mime_type="image/webp",
            size_bytes=10,
            width=1,
            height=1,
            checksum=uuid4().hex * 2,
            kind="listing_image",
        )
        session.add(asset)
        await session.flush()
        if attached:
            session.add(
                ListingImage(
                    listing_id=listings_to_add[0].id,
                    media_asset_id=asset.id,
                    sort_order=0,
                    is_cover=True,
                )
            )
        await session.commit()
        return MediaFixture(
            user_id=user.id,
            first_listing_id=listings_to_add[0].id,
            second_listing_id=listings_to_add[1].id,
            asset_id=asset.id,
            storage_key=storage_key,
        )


async def replace_images(user_id: UUID, listing_id: UUID, asset_ids: list[UUID]) -> int:
    async with SessionLocal() as session:
        user = await session.get(User, user_id)
        assert user is not None
        try:
            await listings.replace_listing_images(
                listing_id,
                ListingImagesRequest(assetIds=asset_ids),
                user,
                session,
            )
        except HTTPException as exc:
            await session.rollback()
            return exc.status_code
        return 200


async def test_delete_and_attach_cannot_leave_a_reference_to_deleted_media(monkeypatch):
    fixture = await create_fixture(attached=False)
    asset_locked = asyncio.Event()
    release_delete = asyncio.Event()
    real_lock = uploads.lock_media_assets

    async def controlled_delete_lock(session, asset_ids):
        assets = await real_lock(session, asset_ids)
        asset_locked.set()
        await release_delete.wait()
        return assets

    monkeypatch.setattr(uploads, "lock_media_assets", controlled_delete_lock)

    async def delete_asset() -> None:
        async with SessionLocal() as session:
            user = await session.get(User, fixture.user_id)
            assert user is not None
            await uploads.delete_upload(fixture.asset_id, user, session)

    delete_task = asyncio.create_task(delete_asset())
    await asyncio.wait_for(asset_locked.wait(), timeout=5)
    attach_task = asyncio.create_task(
        replace_images(fixture.user_id, fixture.first_listing_id, [fixture.asset_id])
    )
    await asyncio.sleep(0.05)
    release_delete.set()

    await delete_task
    assert await attach_task == 422
    async with SessionLocal() as session:
        asset = await session.get(MediaAsset, fixture.asset_id)
        attachment = await session.scalar(
            select(ListingImage).where(ListingImage.media_asset_id == fixture.asset_id)
        )
        job = await session.scalar(
            select(StorageDeletionJob).where(StorageDeletionJob.storage_key == fixture.storage_key)
        )
    assert asset is not None and asset.deleted_at is not None
    assert attachment is None
    assert job is not None


async def test_detach_and_attach_serialize_orphan_detection(monkeypatch):
    fixture = await create_fixture(attached=True)
    asset_locked = asyncio.Event()
    release_detach = asyncio.Event()
    real_lock = listings.lock_media_assets
    paused = False

    async def controlled_listing_lock(session, asset_ids):
        nonlocal paused
        assets = await real_lock(session, asset_ids)
        task = asyncio.current_task()
        if task is not None and task.get_name() == "detach-media" and not paused:
            paused = True
            asset_locked.set()
            await release_detach.wait()
        return assets

    monkeypatch.setattr(listings, "lock_media_assets", controlled_listing_lock)

    detach_task = asyncio.create_task(
        replace_images(fixture.user_id, fixture.first_listing_id, []),
        name="detach-media",
    )
    await asyncio.wait_for(asset_locked.wait(), timeout=5)
    attach_task = asyncio.create_task(
        replace_images(fixture.user_id, fixture.second_listing_id, [fixture.asset_id]),
        name="attach-media",
    )
    await asyncio.sleep(0.05)
    release_detach.set()

    assert await detach_task == 200
    assert await attach_task == 422
    async with SessionLocal() as session:
        asset = await session.get(MediaAsset, fixture.asset_id)
        attachments = (
            await session.scalars(
                select(ListingImage).where(ListingImage.media_asset_id == fixture.asset_id)
            )
        ).all()
    assert asset is not None and asset.deleted_at is not None
    assert attachments == []


async def test_avatar_and_listing_attachment_share_the_same_media_lock(monkeypatch):
    fixture = await create_fixture(attached=False)
    asset_locked = asyncio.Event()
    release_avatar = asyncio.Event()
    real_lock = users.lock_media_assets

    async def controlled_avatar_lock(session, asset_ids):
        assets = await real_lock(session, asset_ids)
        asset_locked.set()
        await release_avatar.wait()
        return assets

    monkeypatch.setattr(users, "lock_media_assets", controlled_avatar_lock)

    async def set_avatar() -> None:
        async with SessionLocal() as session:
            user = await session.get(User, fixture.user_id)
            assert user is not None
            await users.update_avatar(AvatarUpdateRequest(assetId=fixture.asset_id), user, session)

    avatar_task = asyncio.create_task(set_avatar())
    await asyncio.wait_for(asset_locked.wait(), timeout=5)
    attach_task = asyncio.create_task(
        replace_images(fixture.user_id, fixture.first_listing_id, [fixture.asset_id])
    )
    await asyncio.sleep(0.05)
    release_avatar.set()

    await avatar_task
    assert await attach_task == 422
    async with SessionLocal() as session:
        user = await session.get(User, fixture.user_id)
        asset = await session.get(MediaAsset, fixture.asset_id)
        attachment = await session.scalar(
            select(ListingImage).where(ListingImage.media_asset_id == fixture.asset_id)
        )
    assert user is not None and user.avatar_asset_id == fixture.asset_id
    assert asset is not None and asset.deleted_at is None and asset.kind == "avatar"
    assert attachment is None


async def test_database_guard_rejects_a_reference_to_deleted_media():
    fixture = await create_fixture(attached=False)
    async with SessionLocal() as session:
        asset = await session.get(MediaAsset, fixture.asset_id)
        assert asset is not None
        asset.deleted_at = datetime.now(UTC)
        await session.commit()

    async with SessionLocal() as session:
        session.add(
            ListingImage(
                listing_id=fixture.first_listing_id,
                media_asset_id=fixture.asset_id,
                sort_order=0,
                is_cover=True,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


async def test_account_deletion_detaches_owned_media_from_a_foreign_listing():
    fixture = await create_fixture(attached=False)
    async with SessionLocal() as session:
        foreign_owner = User(
            email=f"foreign-media-host-{uuid4()}@example.test",
            password_hash="unused",
            name="Foreign Media Host",
            role="host",
            initials="FM",
            email_verified=True,
        )
        session.add(foreign_owner)
        await session.flush()
        foreign_listing = Listing(
            owner_user_id=foreign_owner.id,
            title="Foreign media listing",
            city="Santa Cruz de Tenerife",
            area="Centro",
            approximate_address="Centro",
            rental_mode="long",
            monthly_price=800,
            location=point(-16.25, 28.46),
            status="published",
        )
        session.add(foreign_listing)
        await session.flush()
        session.add(
            ListingImage(
                listing_id=foreign_listing.id,
                media_asset_id=fixture.asset_id,
                sort_order=0,
                is_cover=True,
            )
        )
        await session.commit()
        foreign_listing_id = foreign_listing.id

    async with SessionLocal() as session:
        owner = await session.get(User, fixture.user_id)
        assert owner is not None
        await users.delete_account(owner, session)

    async with SessionLocal() as session:
        attachment = await session.scalar(
            select(ListingImage).where(ListingImage.media_asset_id == fixture.asset_id)
        )
        foreign_listing = await session.get(Listing, foreign_listing_id)
        asset = await session.get(MediaAsset, fixture.asset_id)
    assert attachment is None
    assert foreign_listing is not None and foreign_listing.deleted_at is None
    assert asset is not None and asset.deleted_at is not None
