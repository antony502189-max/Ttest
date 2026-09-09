from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...models import User
from ...models.moderation import ModerationNotice
from ...schemas.auth import AvatarUpdateRequest, UserResponse, UserUpdateRequest
from ...schemas.moderation import ModerationNoticeResponse, MyRestrictionResponse
from ...services.moderation import SUPPORT_EMAIL, active_user_restriction
from ...services.user_locks import lock_user_for_mutation
from ...services.users import delete_account, update_avatar, update_profile
from ..dependencies import authenticated_user, current_user
from .auth import public_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(authenticated_user)):
    return public_user(user)


@router.get("/me/restriction", response_model=MyRestrictionResponse | None)
async def get_my_restriction(
    user: User = Depends(authenticated_user),
    session: AsyncSession = Depends(get_session),
):
    restriction = await active_user_restriction(user.id, session)
    if not restriction:
        return None
    return MyRestrictionResponse(
        restrictionType=restriction.restriction_type,
        reason=restriction.reason,
        until=restriction.ends_at,
        supportEmail=SUPPORT_EMAIL,
    )


@router.get("/me/moderation-notices", response_model=list[ModerationNoticeResponse])
async def get_my_moderation_notices(
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(authenticated_user),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.scalars(
            select(ModerationNotice)
            .where(ModerationNotice.user_id == user.id)
            .order_by(ModerationNotice.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        ModerationNoticeResponse(
            id=row.id,
            kind=row.kind,
            title=row.title,
            body=row.body,
            createdAt=row.created_at,
            readAt=row.read_at,
        )
        for row in rows
    ]


@router.patch("/me/moderation-notices/{notice_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_moderation_notice_read(
    notice_id: UUID,
    user: User = Depends(authenticated_user),
    session: AsyncSession = Depends(get_session),
):
    locked_user = await lock_user_for_mutation(user.id, session)
    if not locked_user or locked_user.blocked or locked_user.deleted_at is not None:
        raise HTTPException(403, "Account is not active")
    notice = await session.scalar(
        select(ModerationNotice)
        .where(ModerationNotice.id == notice_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )
    if not notice or notice.user_id != user.id:
        raise HTTPException(404, "Notice not found")
    if notice.read_at is None:
        notice.read_at = datetime.now(UTC)
        await session.commit()


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
