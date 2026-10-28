"""Durable lifecycle recovery on real PG, including acknowledgement loss."""
import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, update
from test_http_review import recovery_runtime

from app.main import app
from app.models.ai_search_session import AISearchSession, AISessionCommand
from app.repositories.ai_search_sessions import SessionError
from app.schemas.ai_search_quota import QuotaSubject

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("action", ["create", "reset"])
@pytest.mark.parametrize("cap", [1, 2])
async def test_committed_lifecycle_lost_ack_replays_one_owned_session(store, pg, monkeypatch, action, cap):
    owner, snapshot, *_rest, token = await recovery_runtime(store, monkeypatch, cap=cap)
    # Starting create uses a fresh owner with no occupied slots.
    if action == "create":
        token, owner = app.state.ai_search_runtime.guests.issue()
    key = uuid4()
    original = getattr(store, action)
    first = True
    async def lost_ack(*args, **kwargs):
        nonlocal first
        value = await original(*args, **kwargs)
        if first:
            first = False
            raise OSError("synthetic lost lifecycle acknowledgement")
        return value
    monkeypatch.setattr(store, action, lost_ack)
    path = "/api/v1/ai-search/sessions" + (f"/{snapshot.intent.session_id}/reset" if action == "reset" else "")
    payload = {"idempotency_key": str(key)} | ({"expected_version": 0} if action == "reset" else {})
    async with AsyncClient(transport=ASGITransport(app), base_url="https://testserver", headers={
        "Origin": "https://testserver", "X-AI-Request": "1", "Cookie": "ai_search_guest=" + token}) as client:
        assert (await client.post(path, json=payload)).status_code == 503
        answers = await asyncio.gather(*(client.post(path, json=payload) for _ in range(5)))
        assert all(answer.status_code == 200 for answer in answers)
        ids = {answer.json()["intent"]["session_id"] for answer in answers}
        assert len(ids) == 1
        async with pg[1]() as conn:
            assert await conn.scalar(select(func.count()).select_from(AISearchSession).where(
                AISearchSession.subject_id == owner.id, AISearchSession.closed_at.is_(None))) == 1
            assert await conn.scalar(select(func.count()).select_from(AISessionCommand).where(
                AISessionCommand.subject_id == owner.id)) == 1


async def test_command_fingerprint_owner_expiry_and_cleanup_fail_closed(store, pg):
    owner = QuotaSubject(kind="guest", id=uuid4())
    key = uuid4()
    created = await store.create(owner, idempotency_key=key, max_active=1)
    assert (await store.create(owner, idempotency_key=key, max_active=1)) == created
    with pytest.raises(SessionError, match="SESSION_COMMAND_CONFLICT"):
        await store.reset(owner, created.intent.session_id, 0, idempotency_key=key, max_active=1)
    other = QuotaSubject(kind="guest", id=uuid4())
    other_session = await store.create(other, idempotency_key=key, max_active=1)
    assert other_session.intent.session_id != created.intent.session_id
    with pytest.raises(SessionError, match="SESSION_NOT_FOUND"):
        await store.reset(other, created.intent.session_id, 0, idempotency_key=uuid4(), max_active=1)
    reset_key = uuid4()
    replacement = await store.reset(owner, created.intent.session_id, 0, idempotency_key=reset_key, max_active=1)
    with pytest.raises(SessionError, match="SESSION_COMMAND_CONFLICT"):
        await store.reset(owner, created.intent.session_id, 1, idempotency_key=reset_key, max_active=1)
    cutoff = datetime.now(UTC) - timedelta(seconds=5)
    async with pg[1].begin() as conn:
        await conn.execute(update(AISearchSession).values(expires_at=cutoff - timedelta(seconds=1)))
    with pytest.raises(SessionError, match="SESSION_EXPIRED"):
        await store.reset(owner, created.intent.session_id, 0, idempotency_key=reset_key, max_active=1)
    assert await store.cleanup_unused(older_than=cutoff, limit=100) == 0
    fresh = await store.create(owner, idempotency_key=uuid4(), max_active=1)
    assert fresh.intent.session_id != replacement.intent.session_id


async def test_keyed_create_without_acknowledged_identity_cannot_strand_a_session(store, pg, monkeypatch):
    await recovery_runtime(store, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app), base_url="https://testserver", headers={
        "Origin": "https://testserver", "X-AI-Request": "1"}) as client:
        before = None
        async with pg[1]() as conn:
            before = await conn.scalar(select(func.count()).select_from(AISearchSession))
        payload = {"idempotency_key": str(uuid4())}
        denied = await client.post("/api/v1/ai-search/sessions", json=payload)
        assert denied.status_code == 401 and denied.json()["detail"] == "AI_GUEST_IDENTITY_REQUIRED"
        assert "set-cookie" not in denied.headers
        async with pg[1]() as conn:
            assert await conn.scalar(select(func.count()).select_from(AISearchSession)) == before
        assert (await client.post("/api/v1/ai-search/identity")).status_code == 200
        assert (await client.post("/api/v1/ai-search/sessions", json=payload)).status_code == 200


async def test_failed_reset_rolls_back_source_close_and_receipt_then_same_key_can_retry(store, pg):
    owner = QuotaSubject(kind="auth", id=uuid4())
    source = await store.create(owner, max_active=2)
    other = await store.create(owner, max_active=2)
    key = uuid4()
    with pytest.raises(SessionError, match="SESSION_LIMIT"):
        await store.reset(owner, source.intent.session_id, 0, max_active=1, idempotency_key=key)
    assert await store.get(owner, source.intent.session_id) == source
    async with pg[1]() as conn:
        assert await conn.get(AISessionCommand, (owner.kind, owner.id, key)) is None
    async with pg[1].begin() as conn:
        await conn.execute(update(AISearchSession).where(AISearchSession.id == other.intent.session_id).values(
            expires_at=datetime.now(UTC) - timedelta(seconds=1)))
    fresh = await store.reset(owner, source.intent.session_id, 0, max_active=1, idempotency_key=key)
    assert fresh.intent.session_id != source.intent.session_id
    assert await store.reset(owner, source.intent.session_id, 0, max_active=1, idempotency_key=key) == fresh
