from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Listing, Message, MessageThread, User
from ..repositories.messages import get_or_create_thread, thread_list_query, thread_messages
from ..schemas.messages import MessageResponse, ThreadResponse
from .mail import enqueue_message_notification


def participant(thread: MessageThread, user: User) -> bool:
    return user.id in {thread.tenant_id, thread.host_id}


def public_thread(thread: MessageThread, preview: str | None = None) -> ThreadResponse:
    return ThreadResponse(
        id=thread.id,
        listingId=thread.listing_id,
        tenantId=thread.tenant_id,
        hostId=thread.host_id,
        lastMessageAt=thread.last_message_at,
        createdAt=thread.created_at,
        updatedAt=thread.updated_at,
        lastMessagePreview=preview,
    )


def public_message(message: Message) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        threadId=message.thread_id,
        senderId=message.sender_id,
        body=message.body,
        createdAt=message.created_at,
        readAt=message.read_at,
    )


async def list_user_threads(user: User, session: AsyncSession) -> list[ThreadResponse]:
    rows = (await session.execute(thread_list_query(user.id))).all()
    return [public_thread(thread, preview) for thread, preview in rows]


async def create_initial_message(
    listing_id: UUID,
    body: str,
    user: User,
    session: AsyncSession,
) -> MessageResponse:
    listing = await session.get(Listing, listing_id)
    now = datetime.now(UTC)
    if (
        not listing
        or listing.deleted_at is not None
        or listing.status != "published"
        or (listing.expires_at is not None and listing.expires_at <= now)
    ):
        raise HTTPException(404, "Listing not found")
    if listing.owner_user_id == user.id:
        raise HTTPException(422, "You cannot message your own listing")
    owner = await session.get(User, listing.owner_user_id)
    if not owner or owner.blocked or owner.deleted_at is not None:
        raise HTTPException(404, "Listing not found")
    if not owner.allow_contact_form:
        raise HTTPException(403, "The advertiser does not accept contact-form messages")
    thread = await get_or_create_thread(
        session,
        listing_id=listing.id,
        tenant_id=user.id,
        host_id=listing.owner_user_id,
    )
    return await _append_message(thread, body, user, session, listing)


async def reply_to_thread(
    thread_id: UUID,
    body: str,
    user: User,
    session: AsyncSession,
) -> MessageResponse:
    thread = await session.get(MessageThread, thread_id)
    if not thread or not participant(thread, user):
        raise HTTPException(404, "Thread not found")
    listing = await session.get(Listing, thread.listing_id)
    if not listing:
        raise HTTPException(404, "Thread not found")
    return await _append_message(thread, body, user, session, listing)


async def _append_message(
    thread: MessageThread,
    body: str,
    user: User,
    session: AsyncSession,
    listing: Listing,
) -> MessageResponse:
    value = body.strip()
    if not value:
        raise HTTPException(422, "Message body cannot be empty")
    message = Message(thread_id=thread.id, sender_id=user.id, body=value)
    thread.last_message_at = datetime.now(UTC)
    session.add(message)
    recipient_id = thread.host_id if user.id == thread.tenant_id else thread.tenant_id
    recipient = await session.get(User, recipient_id)
    if recipient and not recipient.blocked and recipient.deleted_at is None and recipient.allow_contact_form:
        enqueue_message_notification(session, recipient.email, str(listing.id))
    await session.commit()
    await session.refresh(message)
    return public_message(message)


async def list_thread_messages(
    thread_id: UUID,
    user: User,
    session: AsyncSession,
) -> list[MessageResponse]:
    thread = await session.get(MessageThread, thread_id)
    if not thread or not participant(thread, user):
        raise HTTPException(404, "Thread not found")
    messages = await thread_messages(session, thread.id)
    now = datetime.now(UTC)
    changed = False
    for message in messages:
        if message.sender_id != user.id and message.read_at is None:
            message.read_at = now
            changed = True
    if changed:
        await session.commit()
    return [public_message(message) for message in messages]
