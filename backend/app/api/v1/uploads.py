import asyncio
import hashlib
import warnings
from datetime import UTC, datetime
from io import BytesIO
from uuid import UUID, uuid4

from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import Settings, get_settings
from ...db.session import get_session
from ...models import Listing, ListingImage, MediaAsset, User
from ...models.moderation import ListingRestriction, UserRestriction
from ...schemas.media import MediaAssetResponse
from ...services.media_lifecycle import lock_media_assets, lock_media_owner
from ...services.moderation import active_window, enforce_listing_view_access, is_admin
from ...services.storage_deletions import enqueue_storage_deletion
from ...services.user_locks import lock_user_for_mutation
from ...storage import get_storage
from ..dependencies import current_user, optional_user

router = APIRouter(tags=["uploads"])
SUPPORTED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
image_processing_slots = asyncio.Semaphore(get_settings().image_processing_concurrency)


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


def validate_and_normalize(content: bytes) -> tuple[bytes, int, int]:
    settings = get_settings()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as probe:
                if probe.format not in SUPPORTED_FORMATS:
                    raise HTTPException(415, "Only JPEG, PNG and WebP images are supported")
                width, height = probe.size
                if (
                    width < 1
                    or height < 1
                    or width > settings.max_image_dimension
                    or height > settings.max_image_dimension
                    or width * height > settings.max_image_pixels
                ):
                    raise HTTPException(422, "Image dimensions are not allowed")
                probe.verify()

            with Image.open(BytesIO(content)) as source:
                source.load()
                normalized = source.convert("RGBA" if "A" in source.getbands() else "RGB")
                output = BytesIO()
                normalized.save(output, format="WEBP", method=6, quality=88)
                return output.getvalue(), width, height
    except Image.DecompressionBombWarning as exc:
        raise HTTPException(422, "Image dimensions are not allowed") from exc
    except Image.DecompressionBombError as exc:
        raise HTTPException(422, "Image dimensions are not allowed") from exc
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise HTTPException(415, "Invalid image file") from exc


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
    # Pillow decoding and WebP encoding are CPU-heavy synchronous operations.
    # Keep them off the event loop and cap concurrent jobs to bound memory use.
    async with image_processing_slots:
        normalized, width, height = await asyncio.to_thread(validate_and_normalize, content)

    # Serialize quota checks with both concurrent uploads and account deletion.
    await lock_media_owner(session, user.id)
    locked_user = await lock_user_for_mutation(user.id, session)
    if not locked_user or locked_user.blocked or locked_user.deleted_at is not None:
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
        new_bytes=len(normalized),
        settings=settings,
    ):
        raise HTTPException(413, "Media storage quota exceeded")

    storage_key = f"{locked_user.id}/{uuid4().hex}.webp"
    storage = get_storage()
    await asyncio.to_thread(storage.put, storage_key, normalized)
    asset = MediaAsset(
        owner_id=locked_user.id,
        storage_key=storage_key,
        mime_type="image/webp",
        size_bytes=len(normalized),
        width=width,
        height=height,
        checksum=hashlib.sha256(normalized).hexdigest(),
        kind="listing_image",
    )
    session.add(asset)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        try:
            await asyncio.to_thread(storage.delete, storage_key)
        except (OSError, BotoCoreError, ClientError):
            await enqueue_storage_deletion(session, storage_key)
            await session.commit()
        raise
    await session.refresh(asset)
    return public_asset(asset)


@router.get("/media/{asset_id}")
async def get_media(
    asset_id: UUID,
    request: Request,
    user: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_session),
):
    asset = await session.get(MediaAsset, asset_id)
    if not asset or asset.deleted_at:
        raise HTTPException(404, "Media not found")
    admin = bool(user and await is_admin(user, session))
    owner_or_admin = bool(user and (user.id == asset.owner_id or admin))
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
    elif asset.kind == "listing_image":
        # A direct media URL is part of public listing browsing. Enforce the
        # requester's view restriction here too, but preserve owner/admin access
        # needed to manage a listing the account is still allowed to publish.
        if not owner_or_admin:
            await enforce_listing_view_access(user, session)
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

    etag = f'"{asset.checksum}"'
    # Visibility is mutable. Permit a private browser cache, but force every
    # reuse to revalidate through FastAPI so unpublishing/blocking takes effect.
    cache_control = "private, max-age=0, must-revalidate" if publicly_visible else "private, no-store"
    headers = {"ETag": etag, "Cache-Control": cache_control, "Vary": "Authorization"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)

    content = await asyncio.to_thread(get_storage().get, asset.storage_key)
    if content is None:
        raise HTTPException(404, "Media not found")
    return Response(content, media_type=asset.mime_type, headers=headers)


@router.delete("/uploads/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_upload(
    asset_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    # Match account deletion's media-owner -> User -> MediaAsset ordering and
    # revalidate the request-scoped identity before changing durable media.
    await lock_media_owner(session, user.id)
    locked_user = await lock_user_for_mutation(user.id, session)
    if not locked_user or locked_user.blocked or locked_user.deleted_at is not None:
        raise HTTPException(403, "Account is not active")
    locked_assets = await lock_media_assets(session, {asset_id})
    asset = locked_assets[0] if locked_assets else None
    admin = await is_admin(locked_user, session)
    if not asset or asset.deleted_at or (asset.owner_id != locked_user.id and not admin):
        raise HTTPException(404, "Media not found")
    active_avatar = await session.scalar(select(User.id).where(User.avatar_asset_id == asset.id).limit(1))
    listing_attachment = await session.scalar(
        select(ListingImage.listing_id).where(ListingImage.media_asset_id == asset.id).limit(1)
    )
    if active_avatar or listing_attachment:
        raise HTTPException(409, "Media is still attached to an active resource")
    asset.deleted_at = datetime.now(UTC)
    await enqueue_storage_deletion(session, asset.storage_key)
    await session.commit()
