import asyncio
import hashlib
import logging
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import Settings, get_settings
from ...core.media_keys import variant_storage_key
from ...db.session import get_session
from ...models import Listing, ListingImage, MediaAsset, User
from ...models.moderation import ListingRestriction, UserRestriction
from ...schemas.media import MediaAssetResponse
from ...services.media_lifecycle import lock_media_assets, lock_media_owner
from ...services.media_processing import PreparedImage, prepare_image, render_variant
from ...services.moderation import active_window, enforce_listing_view_access, is_admin
from ...services.storage_deletions import enqueue_storage_deletion
from ...services.video_processing import SUPPORTED_VIDEO_MIME_TYPES, prepare_video
from ...storage import Storage, get_storage
from ..dependencies import current_user, optional_user

router = APIRouter(tags=["uploads"])
logger = logging.getLogger(__name__)
SUPPORTED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
image_processing_slots = asyncio.Semaphore(get_settings().image_processing_concurrency)
video_processing_slots = asyncio.Semaphore(get_settings().video_processing_concurrency)
VIDEO_READ_CHUNK_BYTES = 1024 * 1024


def parse_video_range(value: str, total_size: int) -> tuple[int, int]:
    if not value.startswith("bytes=") or "," in value:
        raise ValueError("unsupported range")
    raw_start, separator, raw_end = value[6:].partition("-")
    if not separator or (not raw_start and not raw_end):
        raise ValueError("invalid range")
    if raw_start:
        start = int(raw_start)
        end = int(raw_end) if raw_end else total_size - 1
    else:
        suffix = int(raw_end)
        if suffix <= 0:
            raise ValueError("invalid suffix")
        start = max(0, total_size - suffix)
        end = total_size - 1
    if start < 0 or end < start or start >= total_size:
        raise ValueError("unsatisfiable range")
    return start, min(end, total_size - 1, start + VIDEO_READ_CHUNK_BYTES - 1)


def public_asset(asset: MediaAsset) -> MediaAssetResponse:
    return MediaAssetResponse(
        id=asset.id,
        url=f"/api/v1/media/{asset.id}",
        mimeType=asset.mime_type,
        sizeBytes=asset.size_bytes,
        width=asset.width,
        height=asset.height,
        kind=asset.kind,
    )


def media_quota_exceeded(
    *,
    active_assets: int,
    active_bytes: int,
    new_bytes: int,
    settings: Settings,
) -> bool:
    return (
        active_assets >= settings.max_media_assets_per_user
        or active_bytes + new_bytes > settings.max_media_bytes_per_user
    )


async def _store_prepared_image(storage: Storage, storage_key: str, prepared: PreparedImage) -> None:
    objects = [(storage_key, prepared.content), *[
        (variant_storage_key(storage_key, variant), content)
        for variant, content in prepared.variants.items()
    ]]
    results = await asyncio.gather(
        *(
            asyncio.to_thread(storage.put, object_key, object_content)
            for object_key, object_content in objects
        ),
        return_exceptions=True,
    )
    # Wait for every writer before propagating an error so cleanup cannot race
    # a sibling thread that is still creating a derivative object.
    for result in results:
        if isinstance(result, Exception):
            raise result


async def _delete_prepared_image(storage: Storage, storage_key: str) -> None:
    try:
        await asyncio.to_thread(storage.delete, storage_key)
    except (OSError, BotoCoreError, ClientError):
        # BufferedDeleteStorage has already persisted a best-effort retry key.
        logger.exception("media_cleanup_failed", extra={"storage_key": storage_key})


@router.post("/uploads", response_model=MediaAssetResponse, status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    # This generic upload endpoint also feeds the avatar flow: update_avatar can
    # convert a newly uploaded asset from listing_image to avatar. Therefore a
    # publishing restriction must be enforced at listing publication/renewal,
    # not here, otherwise an otherwise-active user could not update their profile.
    settings = get_settings()
    if file.content_type not in SUPPORTED_FORMATS.values():
        raise HTTPException(415, "Only JPEG, PNG and WebP images are supported")
    content = await file.read(settings.max_upload_bytes + 1)
    await file.close()
    if not content or len(content) > settings.max_upload_bytes:
        raise HTTPException(413, "Image is too large")

    # Decode only once and build browser-sized derivatives in one bounded CPU
    # job. The normalized full image is also capped, so phones never upload a
    # 4000-8000px original only for the browser to shrink it again.
    async with image_processing_slots:
        prepared = await asyncio.to_thread(prepare_image, content)

    storage_key = f"{user.id}/{uuid4().hex}.webp"
    storage = get_storage()
    try:
        # Do storage I/O before taking a user/quota row lock. If the account is
        # concurrently deleted or exceeds quota, the unique provisional object
        # is removed after the authoritative locked check below.
        await _store_prepared_image(storage, storage_key, prepared)
    except (OSError, BotoCoreError, ClientError):
        await _delete_prepared_image(storage, storage_key)
        raise

    try:
        # Serialize quota checks with concurrent uploads and account deletion,
        # but no longer keep this transaction open during S3/MinIO writes.
        await lock_media_owner(session, user.id)
        locked_user = await session.scalar(select(User).where(User.id == user.id).with_for_update())
        if not locked_user or locked_user.blocked or locked_user.deleted_at is not None:
            await _delete_prepared_image(storage, storage_key)
            raise HTTPException(403, "Account is not active")
        active_assets, active_bytes = (
            await session.execute(
                select(
                    func.count(MediaAsset.id),
                    func.coalesce(func.sum(MediaAsset.size_bytes), 0),
                ).where(
                    MediaAsset.owner_id == locked_user.id,
                    MediaAsset.deleted_at.is_(None),
                )
            )
        ).one()
        if media_quota_exceeded(
            active_assets=int(active_assets),
            active_bytes=int(active_bytes),
            new_bytes=len(prepared.content),
            settings=settings,
        ):
            await _delete_prepared_image(storage, storage_key)
            raise HTTPException(413, "Media storage quota exceeded")

        asset = MediaAsset(
            owner_id=locked_user.id,
            storage_key=storage_key,
            mime_type="image/webp",
            size_bytes=len(prepared.content),
            width=prepared.width,
            height=prepared.height,
            checksum=hashlib.sha256(prepared.content).hexdigest(),
            perceptual_hash=prepared.perceptual_hash,
            kind="listing_image",
        )
        session.add(asset)
        await session.commit()
    except HTTPException:
        raise
    except Exception:
        await session.rollback()
        await _delete_prepared_image(storage, storage_key)
        # Keep the database deletion queue as a second durable path when Redis
        # buffering is unavailable during a storage outage.
        try:
            await enqueue_storage_deletion(session, storage_key)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("media_cleanup_enqueue_failed", extra={"storage_key": storage_key})
        raise

    await session.refresh(asset)
    return public_asset(asset)


@router.post("/uploads/video", response_model=MediaAssetResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    settings = get_settings()
    content_type = file.content_type or ""
    if content_type not in SUPPORTED_VIDEO_MIME_TYPES:
        filename = (file.filename or "").casefold()
        if filename.endswith(".mov"):
            content_type = "video/quicktime"
        elif filename.endswith((".mp4", ".m4v")):
            content_type = "video/mp4"
        else:
            raise HTTPException(415, "Only MP4 and MOV videos are supported")
    async with video_processing_slots:
        content = await file.read(settings.max_video_upload_bytes + 1)
        await file.close()
        if not content or len(content) > settings.max_video_upload_bytes:
            raise HTTPException(413, "Video is too large")
        prepared = await asyncio.to_thread(prepare_video, content, content_type)
        del content

    storage_key = f"{user.id}/{uuid4().hex}.mp4"
    storage = get_storage()
    try:
        await asyncio.to_thread(storage.put, storage_key, prepared.content, "video/mp4")
    except (OSError, BotoCoreError, ClientError):
        await _delete_prepared_image(storage, storage_key)
        raise

    try:
        await lock_media_owner(session, user.id)
        locked_user = await session.scalar(select(User).where(User.id == user.id).with_for_update())
        if not locked_user or locked_user.blocked or locked_user.deleted_at is not None:
            await _delete_prepared_image(storage, storage_key)
            raise HTTPException(403, "Account is not active")
        active_assets, active_bytes = (
            await session.execute(
                select(
                    func.count(MediaAsset.id),
                    func.coalesce(func.sum(MediaAsset.size_bytes), 0),
                ).where(
                    MediaAsset.owner_id == locked_user.id,
                    MediaAsset.deleted_at.is_(None),
                )
            )
        ).one()
        if media_quota_exceeded(
            active_assets=int(active_assets),
            active_bytes=int(active_bytes),
            new_bytes=len(prepared.content),
            settings=settings,
        ):
            await _delete_prepared_image(storage, storage_key)
            raise HTTPException(413, "Media storage quota exceeded")

        asset = MediaAsset(
            owner_id=locked_user.id,
            storage_key=storage_key,
            mime_type="video/mp4",
            size_bytes=len(prepared.content),
            width=prepared.width,
            height=prepared.height,
            checksum=hashlib.sha256(prepared.content).hexdigest(),
            perceptual_hash=None,
            kind="listing_image",
        )
        session.add(asset)
        await session.commit()
    except HTTPException:
        raise
    except Exception:
        await session.rollback()
        await _delete_prepared_image(storage, storage_key)
        try:
            await enqueue_storage_deletion(session, storage_key)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("video_cleanup_enqueue_failed", extra={"storage_key": storage_key})
        raise

    await session.refresh(asset)
    return public_asset(asset)


@router.get("/media/{asset_id}")
async def get_media(
    asset_id: UUID,
    request: Request,
    user: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_session),
    variant: Literal["full", "card", "thumb"] = "full",
):
    active_owner_restriction = (
        select(UserRestriction.id)
        .where(UserRestriction.user_id == User.id, *active_window(UserRestriction))
        .correlate(User)
        .exists()
    )
    active_listing_restriction = (
        select(ListingRestriction.id)
        .where(ListingRestriction.listing_id == Listing.id, *active_window(ListingRestriction))
        .correlate(Listing)
        .exists()
    )

    if user is None:
        # Anonymous browsing is the hottest media path. Resolve the asset and
        # its current public visibility in one indexed database round-trip
        # instead of loading MediaAsset and then issuing a second query.
        public_avatar = (
            select(User.id)
            .where(
                User.avatar_asset_id == MediaAsset.id,
                User.deleted_at.is_(None),
                User.blocked.is_(False),
            )
            .correlate(MediaAsset)
            .exists()
        )
        public_listing = (
            select(ListingImage.listing_id)
            .join(Listing, Listing.id == ListingImage.listing_id)
            .join(User, User.id == Listing.owner_user_id)
            .where(
                ListingImage.media_asset_id == MediaAsset.id,
                Listing.status == "published",
                Listing.deleted_at.is_(None),
                (Listing.expires_at.is_(None)) | (Listing.expires_at > func.now()),
                User.deleted_at.is_(None),
                User.blocked.is_(False),
                ~active_owner_restriction,
                ~active_listing_restriction,
            )
            .correlate(MediaAsset)
            .exists()
        )
        public_listing_video = (
            select(Listing.id)
            .join(User, User.id == Listing.owner_user_id)
            .where(
                Listing.video_asset_id == MediaAsset.id,
                Listing.status == "published",
                Listing.deleted_at.is_(None),
                (Listing.expires_at.is_(None)) | (Listing.expires_at > func.now()),
                User.deleted_at.is_(None),
                User.blocked.is_(False),
                ~active_owner_restriction,
                ~active_listing_restriction,
            )
            .correlate(MediaAsset)
            .exists()
        )
        asset = await session.scalar(
            select(MediaAsset)
            .where(
                MediaAsset.id == asset_id,
                MediaAsset.deleted_at.is_(None),
                or_(
                    and_(MediaAsset.kind == "avatar", public_avatar),
                    and_(
                        MediaAsset.kind == "listing_image",
                        MediaAsset.mime_type.like("image/%"),
                        public_listing,
                    ),
                    and_(
                        MediaAsset.kind == "listing_image",
                        MediaAsset.mime_type == "video/mp4",
                        public_listing_video,
                    ),
                ),
            )
            .limit(1)
        )
        if not asset:
            raise HTTPException(404, "Media not found")
        owner_or_admin = False
        publicly_visible = True
    else:
        asset = await session.get(MediaAsset, asset_id)
        if not asset or asset.deleted_at:
            raise HTTPException(404, "Media not found")
        admin = bool(await is_admin(user, session))
        owner_or_admin = bool(user.id == asset.owner_id or admin)
        publicly_visible = False
        if asset.kind == "avatar":
            publicly_visible = bool(
                await session.scalar(
                    select(User.id).where(
                        User.avatar_asset_id == asset.id,
                        User.deleted_at.is_(None),
                        User.blocked.is_(False),
                    )
                )
            )
        elif asset.mime_type.startswith("video/"):
            if not owner_or_admin:
                await enforce_listing_view_access(user, session)
            publicly_visible = bool(
                await session.scalar(
                    select(Listing.id)
                    .join(User, User.id == Listing.owner_user_id)
                    .where(
                        Listing.video_asset_id == asset.id,
                        Listing.status == "published",
                        Listing.deleted_at.is_(None),
                        (Listing.expires_at.is_(None)) | (Listing.expires_at > func.now()),
                        User.deleted_at.is_(None),
                        User.blocked.is_(False),
                        ~active_owner_restriction,
                        ~active_listing_restriction,
                    )
                    .limit(1)
                )
            )
        elif asset.kind == "listing_image":
            # Authenticated restricted viewers must still pass their own policy;
            # owners/admins retain private management access.
            if not owner_or_admin:
                await enforce_listing_view_access(user, session)
            publicly_visible = bool(
                await session.scalar(
                    select(ListingImage.listing_id)
                    .join(Listing, Listing.id == ListingImage.listing_id)
                    .join(User, User.id == Listing.owner_user_id)
                    .where(
                        ListingImage.media_asset_id == asset.id,
                        Listing.status == "published",
                        Listing.deleted_at.is_(None),
                        (Listing.expires_at.is_(None)) | (Listing.expires_at > func.now()),
                        User.deleted_at.is_(None),
                        User.blocked.is_(False),
                        ~active_owner_restriction,
                        ~active_listing_restriction,
                    )
                    .limit(1)
                )
            )
        if not owner_or_admin and not publicly_visible:
            raise HTTPException(404, "Media not found")

    etag = f'"{asset.checksum}-{variant}"'
    # Visibility is mutable. Keep immediate revocation semantics: a cached
    # response still revalidates through FastAPI before it can be reused.
    cache_control = "private, max-age=0, must-revalidate" if publicly_visible else "private, no-store"
    headers = {"ETag": etag, "Cache-Control": cache_control, "Vary": "Authorization"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)

    storage = get_storage()
    settings = get_settings()
    if asset.mime_type.startswith("video/"):
        if variant != "full":
            raise HTTPException(400, "Video variants are not supported")
        total_size = int(asset.size_bytes)
        if total_size < 1:
            raise HTTPException(404, "Media not found")
        headers["Accept-Ranges"] = "bytes"
        range_header = request.headers.get("range")
        if range_header:
            try:
                start, end = parse_video_range(range_header, total_size)
            except ValueError:
                return Response(
                    status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                    headers={**headers, "Content-Range": f"bytes */{total_size}"},
                )
            part = await asyncio.to_thread(storage.get_range, asset.storage_key, start, end)
            if part is None:
                raise HTTPException(404, "Media not found")
            expected_length = end - start + 1
            if len(part) != expected_length:
                logger.error(
                    "video_range_length_mismatch",
                    extra={
                        "asset_id": str(asset.id),
                        "storage_key": asset.storage_key,
                        "start": start,
                        "end": end,
                        "expected": expected_length,
                        "actual": len(part),
                    },
                )
                raise HTTPException(502, "Media storage returned an incomplete range")
            range_headers = {
                **headers,
                "Content-Range": f"bytes {start}-{end}/{total_size}",
                "Content-Length": str(len(part)),
            }
            return Response(
                part,
                status_code=status.HTTP_206_PARTIAL_CONTENT,
                media_type=asset.mime_type,
                headers=range_headers,
            )

        first_end = min(total_size, VIDEO_READ_CHUNK_BYTES) - 1
        first_part = await asyncio.to_thread(storage.get_range, asset.storage_key, 0, first_end)
        if first_part is None:
            raise HTTPException(404, "Media not found")
        if len(first_part) != first_end + 1:
            raise HTTPException(502, "Media storage returned an incomplete range")

        def video_chunks():
            yield first_part
            start = first_end + 1
            while start < total_size:
                end = min(start + VIDEO_READ_CHUNK_BYTES, total_size) - 1
                part = storage.get_range(asset.storage_key, start, end)
                if part is None or len(part) != end - start + 1:
                    raise RuntimeError("Media storage returned an incomplete range")
                yield part
                start = end + 1

        headers["Content-Length"] = str(total_size)
        return StreamingResponse(video_chunks(), media_type=asset.mime_type, headers=headers)

    legacy_full_needs_derivative = (
        variant == "full"
        and max(asset.width, asset.height) > settings.media_full_max_dimension
    )
    storage_key = (
        variant_storage_key(asset.storage_key, "full")
        if legacy_full_needs_derivative
        else asset.storage_key
        if variant == "full"
        else variant_storage_key(asset.storage_key, variant)
    )
    content = await asyncio.to_thread(storage.get, storage_key)

    # Assets uploaded before responsive variants existed are upgraded lazily.
    # This includes a capped 2048px full derivative for legacy originals that
    # are still multi-megapixel. The persistent object survives later deploys,
    # so only its first request pays the resize cost.
    if content is None and (variant != "full" or legacy_full_needs_derivative):
        original = await asyncio.to_thread(storage.get, asset.storage_key)
        if original is None:
            raise HTTPException(404, "Media not found")
        async with image_processing_slots:
            generated = await asyncio.to_thread(render_variant, original, variant)
        content = original if generated is None else generated
        if generated is not None:
            try:
                await asyncio.to_thread(storage.put, storage_key, generated)
            except (OSError, BotoCoreError, ClientError):
                logger.exception(
                    "media_variant_persist_failed",
                    extra={"asset_id": str(asset.id), "variant": variant},
                )

    if content is None:
        raise HTTPException(404, "Media not found")
    return Response(content, media_type=asset.mime_type, headers=headers)


@router.delete("/uploads/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_upload(
    asset_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    locked_assets = await lock_media_assets(session, {asset_id})
    asset = locked_assets[0] if locked_assets else None
    admin = await is_admin(user, session)
    if not asset or asset.deleted_at or (asset.owner_id != user.id and not admin):
        raise HTTPException(404, "Media not found")
    active_avatar = await session.scalar(select(User.id).where(User.avatar_asset_id == asset.id).limit(1))
    listing_attachment = await session.scalar(
        select(ListingImage.listing_id).where(ListingImage.media_asset_id == asset.id).limit(1)
    )
    video_attachment = await session.scalar(
        select(Listing.id).where(Listing.video_asset_id == asset.id).limit(1)
    )
    if active_avatar or listing_attachment or video_attachment:
        raise HTTPException(409, "Media is still attached to an active resource")
    asset.deleted_at = datetime.now(UTC)
    await enqueue_storage_deletion(session, asset.storage_key)
    await session.commit()
