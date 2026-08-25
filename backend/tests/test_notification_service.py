from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.models import MailOutbox
from app.services.notifications import create_notification


@pytest.mark.asyncio
async def test_notification_creation_is_idempotent_and_uses_the_existing_outbox() -> None:
    notification_id = uuid4()
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: notification_id)),
        add=MagicMock(),
    )
    recipient = SimpleNamespace(id=uuid4(), email="host@example.test")

    created = await create_notification(
        session,
        recipient=recipient,
        kind="listing_published",
        title="Published",
        body="Your listing is live.",
        entity_listing_id=uuid4(),
        idempotency_key="listing-status:one",
        email_path="/habitacion/example",
    )

    assert created is True
    statement = session.execute.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT (recipient_user_id, idempotency_key) DO NOTHING" in sql
    mail = session.add.call_args.args[0]
    assert isinstance(mail, MailOutbox)
    assert mail.recipient == "host@example.test"
    assert mail.kind == "notification_listing_published"


@pytest.mark.asyncio
async def test_duplicate_notification_does_not_enqueue_another_email() -> None:
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)),
        add=MagicMock(),
    )
    recipient = SimpleNamespace(id=uuid4(), email="host@example.test")

    created = await create_notification(
        session,
        recipient=recipient,
        kind="listing_published",
        title="Published",
        body="Your listing is live.",
        idempotency_key="listing-status:one",
        email_path="/habitacion/example",
    )

    assert created is False
    session.add.assert_not_called()
