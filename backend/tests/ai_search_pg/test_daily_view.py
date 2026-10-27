"""Authoritative read-only quota display, including a Madrid DST boundary."""
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select, text
from test_sessions import complete, operation

import app.repositories.ai_search_quota as quota_module
from app.models.ai_search_quota import AIUsageDay
from app.schemas.ai_search_quota import FailureCode, QuotaSubject

pytestmark = pytest.mark.integration


async def test_empty_status_has_no_writes_and_correct_guest_auth_limits(store, pg, monkeypatch):
    original = quota_module.madrid_window
    async def inspect(session, at=None):
        assert await session.scalar(text("SHOW transaction_read_only")) == "on"
        assert await session.scalar(text("SHOW transaction_isolation")) == "repeatable read"
        return await original(session, at)
    monkeypatch.setattr(quota_module, "madrid_window", inspect)
    identity = uuid4()
    for kind, limit in (("guest", 3), ("auth", 200)):
        status = await store.ledger.daily_status(QuotaSubject(kind=kind, id=identity))
        assert status.limit == status.remaining == limit and status.used == status.reserved == 0
    async with pg[1]() as session:
        assert await session.scalar(select(func.count()).select_from(AIUsageDay)) == 0


async def test_status_reflects_reserve_release_and_success_without_extra_debit(store):
    subject = QuotaSubject(kind="guest", id=uuid4())
    snapshot = await store.create(subject)
    op = operation(snapshot)
    await store.ledger.reserve(subject, op)
    status = await store.ledger.daily_status(subject)
    assert (status.used, status.reserved, status.remaining) == (0, 1, 2)
    claim = await store.ledger.claim(subject, op)
    await store.ledger.release(subject, op, claim.fence, FailureCode.LLM_FAILURE)
    assert (await store.ledger.daily_status(subject)).remaining == 3
    await complete(store, subject, snapshot)
    status = await store.ledger.daily_status(subject)
    assert (status.used, status.reserved, status.remaining) == (1, 0, 2)
    other = await store.ledger.daily_status(QuotaSubject(kind="auth", id=subject.id))
    assert other.remaining == 200 and other.used == 0


async def test_madrid_midnight_after_dst_reads_new_day_without_creating_it(store, pg, monkeypatch):
    original = quota_module.madrid_window
    clock = [datetime(2026, 10, 25, 23, 59, 59, tzinfo=ZoneInfo("Europe/Madrid"))]
    async def selected(session, at=None):
        return await original(session, clock[0])
    monkeypatch.setattr(quota_module, "madrid_window", selected)
    subject = QuotaSubject(kind="guest", id=uuid4())
    await complete(store, subject, await store.create(subject))
    before = await store.ledger.daily_status(subject)
    assert before.used == 1 and before.madrid_date.isoformat() == "2026-10-25"
    assert before.reset_at.astimezone(ZoneInfo("Europe/Madrid")).isoformat() == "2026-10-26T00:00:00+01:00"
    clock[0] = datetime(2026, 10, 26, 0, 0, tzinfo=ZoneInfo("Europe/Madrid"))
    after = await store.ledger.daily_status(subject)
    assert after.remaining == 3 and after.madrid_date.isoformat() == "2026-10-26"
    async with pg[1]() as session:
        assert await session.scalar(select(func.count()).select_from(AIUsageDay)) == 1
