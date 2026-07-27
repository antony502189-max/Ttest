from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...models import Listing, Message, MessageThread, User
from ...schemas.messages import MessageResponse, SendMessageRequest, ThreadResponse
from ...services.mail import enqueue_message_notification
from ..dependencies import current_user

router = APIRouter(prefix="/messages", tags=["messages"])


def participant(thread: MessageThread, user: User) -> bool:
    return user.id in {thread.tenant_id, thread.host_id}


def public_thread(thread: MessageThread, preview: str | None = None) -> ThreadResponse:
    return ThreadResponse(
        id=thread.id, listingId=thread.listing_id, tenantId=thread.tenant_id, hostId=thread.host_id,
        lastMessageAt=thread.last_message_at, createdAt=thread.created_at, updatedAt=thread.updated_at,
        lastMessagePreview=preview,
    )


def public_message(message: Message) -> MessageResponse:
    return MessageResponse(
        id=message.id, threadId=message.thread_id, senderId=message.sender_id, body=message.body,
        createdAt=message.created_at, readAt=message.read_at,
    )


@router.get("/threads", response_model=list[ThreadResponse])
async def list_threads(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    threads = (
        await session.scalars(
            select(MessageThread).where(or_(MessageThread.tenant_id == user.id, MessageThread.host_id == user.id)).order_by(
                MessageThread.last_message_at.desc()
            )
        )
    ).all()
    result: list[ThreadResponse] = []
    for thread in threads:
        preview = await session.scalar(
            select(Message.body).where(Message.thread_id == thread.id, Message.deleted_at.is_(None)).order_by(Message.created_at.desc()).limit(1)
        )
        result.append(public_thread(thread, preview))
    return result


@router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    payload: SendMessageRequest, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
):
    listing = await session.get(Listing, payload.listingId)
    if not listing:
        raise HTTPException(404, "Listing not found")
    if listing.owner_user_id == user.id:
        raise HTTPException(422, "You cannot message your own listing")
    thread = await session.scalar(
        select(MessageThread).where(MessageThread.listing_id == listing.id, MessageThread.tenant_id == user.id)
    )
    if not thread:
        thread = MessageThread(listing_id=listing.id, tenant_id=user.id, host_id=listing.owner_user_id)
        session.add(thread)
        await session.flush()
    message = Message(thread_id=thread.id, sender_id=user.id, body=payload.body.strip())
    thread.last_message_at = datetime.now(UTC)
    session.add(message)
    recipient = await session.get(User, thread.host_id)
    if recipient and recipient.allow_contact_form:
        enqueue_message_notification(session, recipient.email, str(listing.id))
    await session.commit()
    await session.refresh(message)
    return public_message(message)


@router.get("/threads/{thread_id}", response_model=list[MessageResponse])
async def list_messages(thread_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    thread = await session.get(MessageThread, thread_id)
    if not thread or not participant(thread, user):
        raise HTTPException(404, "Thread not found")
    messages = (
        await session.scalars(
            select(Message).where(Message.thread_id == thread.id, Message.deleted_at.is_(None)).order_by(Message.created_at)
        )
    ).all()
    now = datetime.now(UTC)
    for message in messages:
        if message.sender_id != user.id and message.read_at is None:
            message.read_at = now
    await session.commit()
    return [public_message(message) for message in messages]
