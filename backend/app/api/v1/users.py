from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...models import AuthSession, User
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
    await session.execute(update(AuthSession).where(AuthSession.user_id == user.id).values(revoked_at=datetime.now(UTC)))
    await session.delete(user)
    await session.commit()
    response.delete_cookie("refresh_token", path="/api/v1/auth")
