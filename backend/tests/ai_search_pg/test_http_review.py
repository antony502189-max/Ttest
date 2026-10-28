"""Real ledger/session cancellation and issuance policy regressions."""
import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text, update
from test_execution import configured, operation
from test_sessions import usage

from app.api.v1.ai_search import AISearchRuntime
from app.main import app
from app.models.ai_search_quota import AISearchRequest, AIUsageDay
from app.models.ai_search_session import AISearchSession
from app.repositories.ai_search_sessions import SessionError
from app.schemas.ai_search_quota import QuotaSubject
from app.services.ai_guest_tokens import GuestPolicy, GuestTokens
from app.services.ai_http_policy import AIHTTPPolicy

pytestmark = pytest.mark.integration


async def test_subject_session_bound_is_atomic_and_cleanup_is_explicit_and_bounded(store, pg):
    subject = QuotaSubject(kind="auth", id=uuid4())
    async def create():
        try:
            return await store.create(subject, max_active=2)
        except SessionError as error:
            assert error.code == "SESSION_LIMIT" and error.retry_after > 0
            return None
    attempts = await asyncio.gather(*(create() for _ in range(110)))
    assert len([value for value in attempts if value is not None]) == 2
    async with pg[1]() as conn:
        assert await conn.scalar(select(func.count()).select_from(AISearchSession)) == 2
        assert await conn.scalar(select(func.count()).select_from(AIUsageDay)) == 0
    snapshot = next(value for value in attempts if value is not None)
    reset = await store.reset(subject, snapshot.intent.session_id, 0, max_active=2)
    assert reset.intent.session_id != snapshot.intent.session_id
    # A separate subject has its own bound; neither session mint nor cleanup
    # resets the LLM quota or deletes operation audit.
    other = QuotaSubject(kind="guest", id=uuid4())
    referenced = await store.create(other, max_active=1)
    await store.ledger.reserve(other, operation(referenced))
    cutoff = datetime.now(UTC) - timedelta(hours=1)
    async with pg[1].begin() as conn:
        await conn.execute(update(AISearchSession).values(expires_at=cutoff - timedelta(seconds=1)))
    assert await store.cleanup_unused(older_than=cutoff, limit=1) == 1
    assert await store.cleanup_unused(older_than=cutoff, limit=10) == 2
    assert await store.cleanup_unused(older_than=cutoff, limit=10) == 0
    async with pg[1]() as conn:
        assert await conn.scalar(select(func.count()).select_from(AISearchSession)) == 1
        assert await conn.scalar(select(func.count()).select_from(AISearchRequest)) == 1
        assert await conn.scalar(select(func.count()).select_from(AIUsageDay)) == 1
    with pytest.raises(ValueError):
        await store.cleanup_unused(older_than=datetime.now(UTC) + timedelta(days=1), limit=1)


@pytest.mark.parametrize("phase", ["parser", "query", "before_commit", "after_commit"])
async def test_http_timeout_has_phase_safe_release_rollback_or_replay(store, pg, monkeypatch, phase):
    subject, snapshot, parser, gate, query, execution = await configured(store)
    started = asyncio.Event()
    async def block():
        started.set()
        await asyncio.Event().wait()
    if phase == "parser":
        parser.finish = asyncio.Event()
    elif phase == "query":
        query.finish = asyncio.Event()
    elif phase == "before_commit":
        real_commit = store.commit_patch
        def delayed_commit(*args):
            commit = real_commit(*args)
            async def callback(*values):
                await commit(*values)
                await block()  # uncommitted session CAS/result must roll back
            return callback
        monkeypatch.setattr(store, "commit_patch", delayed_commit)
    else:
        real_finalize = store.finalize_patch
        async def lost_ack(*args):
            await real_finalize(*args)
            await block()  # debit already committed, release would be wrong
        monkeypatch.setattr(store, "finalize_patch", lost_ack)
    guests = GuestTokens(key=b"synthetic-guest-key-not-secret-32", policy=GuestPolicy(ttl_seconds=600))
    # Sign the already-created synthetic subject without introducing an auth DB.
    token, cookie_owner = guests.issue()
    async with pg[1].begin() as conn:
        await conn.execute(update(AISearchSession).where(AISearchSession.id == snapshot.intent.session_id).values(
            subject_id=cookie_owner.id))
    subject = cookie_owner
    active = AISearchRuntime(store, SimpleNamespace(sessions=store), execution, guests, gate,
        frozenset({"https://testserver"}), 4096, AIHTTPPolicy(.5, 2, (), "https://testserver"))
    monkeypatch.setattr(app.state, "ai_search_runtime", active, raising=False)
    op = operation(snapshot)
    payload = {"idempotency_key": str(op.idempotency_key), "session_id": str(op.session_id),
        "expected_version": 0, "text": "synthetic message"}
    async with AsyncClient(transport=ASGITransport(app), base_url="https://testserver", headers={
        "Origin": "https://testserver", "X-AI-Request": "1", "Cookie": "ai_search_guest=" + token}) as client:
        response = await client.post("/api/v1/ai-search/query", json=payload)
        assert response.status_code == 504, response.text
        assert response.json()["detail"] == "AI_REQUEST_TIMEOUT_RETRY_SAME_OPERATION"
        if phase != "after_commit":
            if phase == "before_commit":
                assert started.is_set()
            assert await usage(pg, subject) == (0, 1)
            assert (await store.get(subject, op.session_id)).intent.version == 0
            async with pg[1].begin() as conn:
                await conn.execute(text("UPDATE ai_search_requests SET lease_until=clock_timestamp()-interval '2 seconds', "
                    "recover_after=clock_timestamp()-interval '1 second'"))
            assert (await store.ledger.recover(subject, op.idempotency_key)).status == "failed"
        expected = (1, 0) if phase == "after_commit" else (0, 0)
        assert await usage(pg, subject) == expected
        replay = await client.post("/api/v1/ai-search/query", json=payload)
        assert replay.status_code == 200, replay.text
        assert replay.json()["replay"] is True
        assert replay.json()["operation"]["status"] == ("succeeded" if phase == "after_commit" else "failed")
        assert parser.calls == 1
        assert await usage(pg, subject) == expected


async def test_quota_exhaustion_carries_database_madrid_retry_after(store, pg):
    subject, snapshot, _parser, _gate, _query, execution = await configured(store)
    from app.repositories.ai_search_quota import QuotaError
    from app.schemas.listings import ListingCardSearchRequest
    for _ in range(3):
        current = await store.get(subject, snapshot.intent.session_id)
        assert (await execution.execute(subject, operation(current), "synthetic message", ListingCardSearchRequest())).operation.status == "succeeded"
    with pytest.raises(QuotaError) as caught:
        current = await store.get(subject, snapshot.intent.session_id)
        await execution.execute(subject, operation(current), "synthetic message", ListingCardSearchRequest())
    assert caught.value.code == "QUOTA_EXHAUSTED" and 1 <= caught.value.retry_after <= 90_000



async def recovery_runtime(store, monkeypatch, *, cap=1):
    subject, snapshot, parser, gate, query, execution = await configured(store)
    guests = GuestTokens(key=b"synthetic-guest-key-not-secret-32", policy=GuestPolicy(ttl_seconds=600))
    token, owner = guests.issue()
    async with store.ledger.sessions.begin() as conn:
        await conn.execute(update(AISearchSession).where(AISearchSession.id == snapshot.intent.session_id)
                           .values(subject_id=owner.id))
    active = AISearchRuntime(store, SimpleNamespace(sessions=store), execution, guests, gate,
        frozenset({"https://testserver"}), 65536, AIHTTPPolicy(10, cap, (), "https://testserver"))
    monkeypatch.setattr(app.state, "ai_search_runtime", active, raising=False)
    return owner, snapshot, parser, gate, query, execution, token


async def test_lost_ack_expired_success_returns_durable_receipt_without_cards(store, pg, monkeypatch):
    owner, snapshot, parser, gate, query, execution, token = await recovery_runtime(store, monkeypatch)
    real_finalize = store.finalize_patch
    async def lost_ack(*args, **kwargs):
        await real_finalize(*args, **kwargs)
        raise OSError("synthetic lost acknowledgement")
    monkeypatch.setattr(store, "finalize_patch", lost_ack)
    op = operation(snapshot)
    payload = {"idempotency_key": str(op.idempotency_key), "session_id": str(op.session_id),
               "expected_version": 0, "text": "synthetic message"}
    async with AsyncClient(transport=ASGITransport(app), base_url="https://testserver", headers={
        "Origin": "https://testserver", "X-AI-Request": "1", "Cookie": "ai_search_guest=" + token}) as client:
        assert (await client.post("/api/v1/ai-search/query", json=payload)).status_code == 503
        async with pg[1].begin() as conn:
            await conn.execute(update(AISearchSession).where(AISearchSession.id == op.session_id).values(
                expires_at=datetime.now(UTC) - timedelta(seconds=1)))
        for _ in range(3):
            replay = await client.post("/api/v1/ai-search/query", json=payload)
            assert replay.status_code == 200, replay.text
            answer = replay.json()
            assert answer["operation"]["status"] == "succeeded" and answer["replay"]
            assert answer["operation"]["receipt"]["count"] == 3
            assert answer["cards"] is None and answer["cards_error"] == "RESULT_EXPIRED_REQUERY_REQUIRED"
            assert await usage(pg, owner) == (1, 0)
        assert parser.calls == query.calls == 1
        assert gate.calls == 5  # four HTTP requests plus one inference attempt
        async with pg[1]() as conn:
            assert await conn.scalar(select(func.count()).select_from(AISearchRequest)) == 1
        ref = answer["operation"]["receipt"]["result_ref"]
        with pytest.raises(SessionError, match="RESULT_EXPIRED_REQUERY_REQUIRED"):
            await store.result(owner, UUID(ref))
        assert (await client.get(f"/api/v1/ai-search/sessions/{op.session_id}")).json() == {"detail": "SESSION_EXPIRED"}
        assert (await client.get(f"/api/v1/ai-search/sessions/{uuid4()}")).status_code == 404


@pytest.mark.parametrize("cap", [1, 2])
async def test_http_repeated_explicit_reset_does_not_accumulate_active_sessions(store, pg, monkeypatch, cap):
    owner, snapshot, *_rest, token = await recovery_runtime(store, monkeypatch, cap=cap)
    sid = snapshot.intent.session_id
    async with AsyncClient(transport=ASGITransport(app), base_url="https://testserver", headers={
        "Origin": "https://testserver", "X-AI-Request": "1", "Cookie": "ai_search_guest=" + token}) as client:
        for _ in range(4):
            response = await client.post(f"/api/v1/ai-search/sessions/{sid}/reset", json={"expected_version": 0})
            assert response.status_code == 200, response.text
            fresh = response.json()["intent"]["session_id"]
            assert fresh != str(sid)
            assert (await client.get(f"/api/v1/ai-search/sessions/{sid}")).status_code == 409
            sid = fresh
            async with pg[1]() as conn:
                assert await conn.scalar(select(func.count()).select_from(AISearchSession).where(
                    AISearchSession.closed_at.is_(None), AISearchSession.subject_id == owner.id)) == 1
            assert await usage(pg, owner) == (None, None)


@pytest.mark.parametrize("bad_cookie", ["forged", "expired"])
async def test_invalid_guest_cookie_is_deleted_then_explicit_create_passes_issuance_gates(store, pg, monkeypatch, bad_cookie):
    _owner, snapshot, _parser, gate, _query, _execution, _token = await recovery_runtime(store, monkeypatch)
    active = app.state.ai_search_runtime
    invalid = "forged" if bad_cookie == "forged" else active.guests.issue(now=1)[0]
    async with AsyncClient(transport=ASGITransport(app), base_url="https://testserver", headers={
        "Origin": "https://testserver", "X-AI-Request": "1"}) as client:
        client.cookies.set("ai_search_guest", invalid, domain="testserver.local", path="/api/v1/ai-search")
        rejected = await client.get(f"/api/v1/ai-search/sessions/{snapshot.intent.session_id}")
        assert rejected.status_code == 401 and rejected.json()["detail"] == "AI_GUEST_IDENTITY_INVALID_OR_EXPIRED"
        assert "Max-Age=0" in rejected.headers["set-cookie"]
        assert not list(client.cookies)
        before = gate.calls
        created = await client.post("/api/v1/ai-search/sessions")
        assert created.status_code == 200, created.text
        assert gate.calls == before + 3  # HTTP, guest issuance IP, session creation
        new_owner = active.guests.read(client.cookies.get("ai_search_guest"))
        assert await usage(pg, new_owner) == (None, None)
        assert (await client.get(f"/api/v1/ai-search/sessions/{snapshot.intent.session_id}")).status_code == 404
        # A malformed cookie on create also only clears it; it never mints in place.
        denied = await client.post("/api/v1/ai-search/sessions", headers={"Cookie": "ai_search_guest=forged"})
        assert denied.status_code == 401 and "Max-Age=0" in denied.headers["set-cookie"]
