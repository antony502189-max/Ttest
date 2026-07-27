import hashlib
from io import BytesIO
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import get_settings
from ...db.session import get_session
from ...models import MediaAsset, User
from ...schemas.media import MediaAssetResponse
from ..dependencies import current_user

router = APIRouter(tags=["uploads"])
SUPPORTED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


def public_asset(asset: MediaAsset) -> MediaAssetResponse:
    return MediaAssetResponse(
        id=asset.id, url=f"/api/v1/media/{asset.id}", mimeType=asset.mime_type, sizeBytes=asset.size_bytes,
        width=asset.width, height=asset.height, kind=asset.kind,
    )


def validate_and_normalize(content: bytes) -> tuple[bytes, int, int]:
    try:
        with Image.open(BytesIO(content)) as source:
            source.load()
            if source.format not in SUPPORTED_FORMATS:
                raise HTTPException(415, "Only JPEG, PNG and WebP images are supported")
            width, height = source.size
            settings = get_settings()
            if width < 1 or height < 1 or width > settings.max_image_dimension or height > settings.max_image_dimension:
                raise HTTPException(422, "Image dimensions are not allowed")
            normalized = source.convert("RGBA" if "A" in source.getbands() else "RGB")
            output = BytesIO()
            normalized.save(output, format="WEBP", method=6, quality=88)
            return output.getvalue(), width, height
    except UnidentifiedImageError:
        raise HTTPException(415, "Invalid image file")


@router.post("/uploads", response_model=MediaAssetResponse, status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile = File(...), user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
):
    settings = get_settings()
    if file.content_type not in SUPPORTED_FORMATS.values():
        raise HTTPException(415, "Only JPEG, PNG and WebP images are supported")
    content = await file.read(settings.max_upload_bytes + 1)
    if not content or len(content) > settings.max_upload_bytes:
        raise HTTPException(413, "Image is too large")
    normalized, width, height = validate_and_normalize(content)
    storage_key = f"{uuid4().hex}.webp"
    destination = settings.media_root / storage_key
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(normalized)
    asset = MediaAsset(
        owner_id=user.id, storage_key=storage_key, mime_type="image/webp", size_bytes=len(normalized), width=width,
        height=height, checksum=hashlib.sha256(normalized).hexdigest(), kind="listing_image",
    )
    session.add(asset)
    try:
        await session.commit()
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    await session.refresh(asset)
    return public_asset(asset)


@router.get("/media/{asset_id}")
async def get_media(asset_id: UUID, session: AsyncSession = Depends(get_session)):
    asset = await session.get(MediaAsset, asset_id)
    if not asset or asset.deleted_at:
        raise HTTPException(404, "Media not found")
    path = get_settings().media_root / asset.storage_key
    if not path.is_file():
        raise HTTPException(404, "Media not found")
    return FileResponse(path, media_type=asset.mime_type, filename=f"{asset.id}.webp")


@router.delete("/uploads/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_upload(asset_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    asset = await session.get(MediaAsset, asset_id)
    if not asset or asset.owner_id != user.id:
        raise HTTPException(404, "Media not found")
    path = get_settings().media_root / asset.storage_key
    await session.delete(asset)
    await session.commit()
    path.unlink(missing_ok=True)
