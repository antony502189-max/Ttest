from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import get_settings
from ...db.session import get_session
from ...models import AuthSession, Listing, MediaAsset, User
from ...schemas.auth import UserResponse, UserUpdateRequest
from ..dependencies import current_user
from .auth import public_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(current_user)):
    return public_user(user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    payload: UserUpdateRequest, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
):
    fields = payload.model_dump(exclude_unset=True)
    mapping = {
        "showPhone": "show_phone", "showWhatsApp": "show_whatsapp", "allowContactForm": "allow_contact_form",
    }
    for key, value in fields.items():
        setattr(user, mapping.get(key, key), value.strip() if isinstance(value, str) else value)
    if "name" in fields:
        user.initials = "".join(part[:1].upper() for part in user.name.split()[:2])
    await session.commit()
    await session.refresh(user)
    return public_user(user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    response: Response, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
):
    media_paths = list((await session.scalars(select(MediaAsset.storage_key).where(MediaAsset.owner_id == user.id))).all())
    await session.execute(update(AuthSession).where(AuthSession.user_id == user.id).values(revoked_at=datetime.now(UTC)))
    await session.execute(delete(Listing).where(Listing.owner_user_id == user.id))
    await session.delete(user)
    await session.commit()
    for storage_key in media_paths:
        (get_settings().media_root / storage_key).unlink(missing_ok=True)
    response.delete_cookie("refresh_token", path="/api/v1/auth")
