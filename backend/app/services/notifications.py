from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Notification, User
from ..schemas.notifications import NotificationPage, NotificationResponse
from .mail import enqueue_mail, frontend_link


def _response(notification: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id,
        type=notification.type,
        entityListingId=notification.entity_listing_id,
        title=notification.title,
        body=notification.body,
        createdAt=notification.created_at,
        readAt=notification.read_at,
    )


async def create_notification(
    session: AsyncSession,
    *,
    recipient: User,
    kind: str,
    title: str,
    body: str,
    entity_listing_id: UUID | None = None,
    idempotency_key: str,
    email_path: str | None = None,
) -> bool:
    """Persist a notification and fan out through the existing outbox once."""
    result = await session.execute(
        insert(Notification)
        .values(
            recipient_user_id=recipient.id,
            type=kind,
            entity_listing_id=entity_listing_id,
            title=title,
            body=body,
            idempotency_key=idempotency_key,
        )
        .on_conflict_do_nothing(index_elements=["recipient_user_id", "idempotency_key"])
        .returning(Notification.id)
    )
    created = result.scalar_one_or_none() is not None
    if created and email_path:
        enqueue_mail(
            session,
            kind=f"notification_{kind}",
            recipient=recipient.email,
            subject=title,
            body=f"{body}\n\n{frontend_link(email_path)}",
        )
    return created


async def list_notifications(user: User, session: AsyncSession, *, limit: int, offset: int) -> NotificationPage:
    unread = await session.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.recipient_user_id == user.id,
            Notification.read_at.is_(None),
        )
    )
    items = list((await session.scalars(
        select(Notification)
        .where(Notification.recipient_user_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
        .offset(offset)
    )).all())
    return NotificationPage(items=[_response(item) for item in items], unreadCount=int(unread or 0))


async def mark_notification_read(notification_id: UUID, user: User, session: AsyncSession) -> None:
    result = await session.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.recipient_user_id == user.id)
        .values(read_at=datetime.now(UTC))
    )
    if result.rowcount != 1:
        raise HTTPException(404, "Notification not found")
    await session.commit()


async def mark_all_notifications_read(user: User, session: AsyncSession) -> None:
    await session.execute(
        update(Notification)
        .where(Notification.recipient_user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    await session.commit()
