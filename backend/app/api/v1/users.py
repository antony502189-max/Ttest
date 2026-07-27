from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...models import User
from ...schemas.auth import AvatarUpdateRequest, UserResponse, UserUpdateRequest
from ...services.users import delete_account, update_avatar, update_profile
from ..dependencies import current_user
from .auth import public_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(current_user)):
    return public_user(user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    payload: UserUpdateRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return public_user(await update_profile(payload, user, session))


@router.put("/me/avatar", response_model=UserResponse)
async def update_me_avatar(
    payload: AvatarUpdateRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return public_user(await update_avatar(payload, user, session))


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    response: Response,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await delete_account(user, session)
    response.delete_cookie("refresh_token", path="/api/v1/auth")
