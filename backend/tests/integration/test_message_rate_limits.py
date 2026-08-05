from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import Listing, Message, MessageThread, User
from app.repositories.listings import point
from app.services import messages

pytestmark = pytest.mark.integration


async def create_fixture() -> tuple[UUID, UUID]:
    async with SessionLocal() as session:
        tenant = User(
            email=f"message-tenant-{uuid4()}@example.test",
            password_hash="unused",
            name="Message Tenant",
            role="tenant",
            initials="MT",
            email_verified=True,
        )
        host = User(
            email=f"message-host-{uuid4()}@example.test",
            password_hash="unused",
            name="Message Host",
            role="host",
            initials="MH",
            email_verified=True,
        )
        session.add_all([tenant, host])
        await session.flush()
        listing = Listing(
            owner_user_id=host.id,
            title="Message quota listing",
            city="Santa Cruz de Tenerife",
            area="Centro",
            approximate_address="Centro",
            rental_mode="long",
            monthly_price=700,
            location=point(-16.25, 28.46),
            status="published",
        )
        session.add(listing)
        await session.flush()
        thread = MessageThread(
            listing_id=listing.id,
            tenant_id=tenant.id,
            host_id=host.id,
        )
        session.add(thread)
        await session.commit()
        return tenant.id, thread.id


async def send_message(user_id: UUID, thread_id: UUID, index: int) -> int:
    async with SessionLocal() as session:
        user = await session.get(User, user_id)
        assert user is not None
        try:
            await messages.reply_to_thread(thread_id, f"message-{index}", user, session)
        except HTTPException as exc:
            await session.rollback()
            return exc.status_code
        return 201


async def test_concurrent_message_sends_respect_strict_per_account_budget(monkeypatch):
    monkeypatch.setattr(messages, "MAX_MESSAGES_PER_MINUTE", 3)
    user_id, thread_id = await create_fixture()

    outcomes = await asyncio.gather(*(send_message(user_id, thread_id, index) for index in range(8)))

    assert outcomes.count(201) == 3
    assert outcomes.count(429) == 5
    async with SessionLocal() as session:
        stored = await session.scalar(
            select(func.count()).select_from(Message).where(Message.sender_id == user_id)
        )
    assert stored == 3
