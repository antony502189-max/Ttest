from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Message, MessageThread


def thread_list_query(user_id: UUID, *, limit: int, offset: int) -> Select:
    latest_message = (
        select(Message.body)
        .where(Message.thread_id == MessageThread.id, Message.deleted_at.is_(None))
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(1)
        .correlate(MessageThread)
        .scalar_subquery()
    )
    return (
        select(MessageThread, latest_message.label("last_message_preview"))
        .where(or_(MessageThread.tenant_id == user_id, MessageThread.host_id == user_id))
        .order_by(MessageThread.last_message_at.desc(), MessageThread.id)
        .limit(limit)
        .offset(offset)
    )


async def find_thread(session: AsyncSession, listing_id: UUID, tenant_id: UUID) -> MessageThread | None:
    return await session.scalar(
        select(MessageThread).where(
            MessageThread.listing_id == listing_id,
            MessageThread.tenant_id == tenant_id,
        )
    )


async def get_or_create_thread(
    session: AsyncSession,
    *,
    listing_id: UUID,
    tenant_id: UUID,
    host_id: UUID,
) -> MessageThread:
    await session.execute(
        insert(MessageThread)
        .values(listing_id=listing_id, tenant_id=tenant_id, host_id=host_id)
        .on_conflict_do_nothing(constraint="uq_thread_listing_tenant")
    )
    thread = await find_thread(session, listing_id, tenant_id)
    if thread is None:  # pragma: no cover - defensive database invariant
        raise RuntimeError("Message thread could not be created")
    return thread


async def thread_messages(
    session: AsyncSession,
    thread_id: UUID,
    *,
    limit: int,
    offset: int,
) -> list[Message]:
    # Read the newest bounded page, then restore chronological display order.
    # This prevents a long-lived thread from loading its complete history into
    # memory while keeping the existing response shape for the frontend.
    messages = list(
        (
            await session.scalars(
                select(Message)
                .where(Message.thread_id == thread_id, Message.deleted_at.is_(None))
                .order_by(Message.created_at.desc(), Message.id.desc())
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )
    messages.reverse()
    return messages
