from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...models import User
from ...schemas.messages import MessageResponse, ReplyMessageRequest, SendMessageRequest, ThreadResponse
from ...services.messages import (
    create_initial_message,
    list_thread_messages,
    list_user_threads,
    reply_to_thread,
)
from ..dependencies import current_user

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/threads", response_model=list[ThreadResponse])
async def list_threads(
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return await list_user_threads(user, session, limit=limit, offset=offset)


@router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    payload: SendMessageRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return await create_initial_message(payload.listingId, payload.body, user, session)


@router.post("/threads/{thread_id}", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def reply_message(
    thread_id: UUID,
    payload: ReplyMessageRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return await reply_to_thread(thread_id, payload.body, user, session)


@router.get("/threads/{thread_id}", response_model=list[MessageResponse])
async def list_messages(
    thread_id: UUID,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return await list_thread_messages(thread_id, user, session, limit=limit, offset=offset)
