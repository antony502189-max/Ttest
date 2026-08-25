from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...models import User
from ...schemas.notifications import NotificationPage
from ...services.notifications import list_notifications, mark_all_notifications_read, mark_notification_read
from ..dependencies import current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationPage)
async def notifications(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10_000),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return await list_notifications(user, session, limit=limit, offset=offset)


@router.patch("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(notification_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await mark_notification_read(notification_id, user, session)


@router.patch("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await mark_all_notifications_read(user, session)
