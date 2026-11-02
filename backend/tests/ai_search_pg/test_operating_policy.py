"""Retention, expiry, admission and replay on isolated real PostgreSQL."""
import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, update
from test_execution import configured, operation
from test_sessions import complete, usage

from app.models.ai_search_quota import AISearchRequest, AIUsageDay
from app.models.ai_search_session import AISearchSession
from app.repositories.ai_search_quota import QuotaError
from app.repositories.ai_search_sessions import SessionError, SessionPolicy
from app.schemas.ai_clarification import IntentClarification
from app.schemas.ai_search_quota import QuotaSubject
from app.schemas.listings import ListingCardSearchRequest
from app.services.ai_retention import AIRetention
from app.services.ai_search_execution import TextSearchExecution

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("code", ["SOURCE_COVERAGE_UNAVAILABLE", "INTENT_CLARIFICATION_REQUIRED",
    "INTENT_NO_CHANGE", "INTENT_UNSUPPORTED"])
async def test_unavailable_and_provider_decisions_are_terminal_free_and_replayable(store, pg, code):
    from app.repositories.ai_verified_cards import SourceCoverageUnavailable
    from app.services.ai_deepseek_intent import ProviderFailure
    subject, snapshot, parser, gate, query, service = await configured(store)
    if code == "SOURCE_COVERAGE_UNAVAILABLE":
        query.error = SourceCoverageUnavailable(code)
    else:
        parser.error = ProviderFailure(code)
    op = operation(snapshot)
    first = await service.execute(subject, op, "synthetic message", ListingCardSearchRequest())
    assert first.operation.status == "failed" and first.operation.failure_code == code
    assert first.cards is None and await usage(pg, subject) == (0, 0)
    assert await store.get(subject, snapshot.intent.session_id) == snapshot
    replay = await service.execute(subject, op, "synthetic message", ListingCardSearchRequest())
    assert replay.replay and replay.operation == first.operation
    assert parser.calls == gate.calls == 1


async def test_retention_erases_private_criteria_without_reopening_keyed_commands(store, pg):
    from app.models.ai_search_session import AISessionCommand
    owner, key = QuotaSubject(kind="guest", id=uuid4()), uuid4()
    original = await store.create(owner, idempotency_key=key)
    await complete(store, owner, original, {"balcony": {"strength": "hard", "value": True}})
    async with pg[1].begin() as conn:
        await conn.execute(update(AISearchSession).values(expires_at=func.clock_timestamp() - timedelta(days=2)))
    await AIRetention(store).prune()
    async with pg[1]() as conn:
        row = await conn.get(AISearchSession, original.intent.session_id)
        assert row.criteria == {} and row.closed_at is not None
        assert await conn.scalar(select(func.count()).select_from(AISessionCommand)) == 1
    with pytest.raises(SessionError, match="SESSION_EXPIRED"):
        await store.create(owner, idempotency_key=key)
    async with pg[1].begin() as conn:
        await conn.execute(update(AISessionCommand).values(created_at=func.clock_timestamp() - timedelta(days=31)))
    await AIRetention(store).prune()
    await AIRetention(store).prune()
    async with pg[1]() as conn:
        assert await conn.get(AISearchSession, original.intent.session_id) is None


async def test_absolute_lifetime_caps_commit_and_does_not_renew_on_get(store, pg):
    subject = QuotaSubject(kind="auth", id=uuid4())
    initial = await store.create(subject)
    async with pg[1].begin() as conn:
        created = await conn.scalar(update(AISearchSession).where(AISearchSession.id == initial.intent.session_id)
            .values(created_at=func.clock_timestamp() - timedelta(days=7) + timedelta(minutes=5))
            .returning(AISearchSession.created_at))
    await complete(store, subject, initial, {"balcony": {"strength": "hard", "value": True}})
    current = await store.get(subject, initial.intent.session_id)
    assert current.expires_at == created + timedelta(days=7)
    assert (await store.get(subject, initial.intent.session_id)).expires_at == current.expires_at
    async with pg[1].begin() as conn:
        await conn.execute(update(AISearchSession).values(created_at=func.clock_timestamp() - timedelta(days=8),
            expires_at=func.clock_timestamp() + timedelta(days=1)))
    with pytest.raises(SessionError, match="SESSION_EXPIRED"):
        await store.get(subject, initial.intent.session_id)


async def test_gc_deletes_private_state_preserves_status_and_never_reinfers(store, pg):
    subject, snapshot, parser, gate, query, service = await configured(store)
    op = operation(snapshot)
    first = await service.execute(subject, op, "synthetic message", ListingCardSearchRequest())
    async with pg[1].begin() as conn:
        await conn.execute(update(AISearchSession).values(expires_at=func.clock_timestamp() - timedelta(days=2)))
    outcome = await AIRetention(store).prune()
    assert (outcome.sessions, outcome.results, outcome.requests) == (1, 1, 0)
    assert await AIRetention(store).prune() == type(outcome)(0, 0, 0, 0)
    status = await store.ledger.operation_status(subject, op.idempotency_key)
    assert status.status == "succeeded" and status.receipt == first.operation.receipt
    replay = await service.execute(subject, op, "synthetic message", ListingCardSearchRequest())
    assert replay.replay and replay.result_unavailable and replay.cards is None
    assert replay.operation.receipt == first.operation.receipt
    assert parser.calls == gate.calls == query.calls == 1
    assert await usage(pg, subject) == (1, 0)
    with pytest.raises(QuotaError, match="OPERATION_NOT_FOUND"):
        await store.ledger.operation_status(QuotaSubject(kind="auth", id=subject.id), op.idempotency_key)
    with pytest.raises(QuotaError, match="OPERATION_NOT_FOUND"):
        await store.ledger.operation_status(QuotaSubject(kind="guest", id=uuid4()), op.idempotency_key)


async def test_expired_key_after_tombstone_gc_cannot_become_new_search(store, pg):
    subject, snapshot, parser, _gate, _query, service = await configured(store)
    op = operation(snapshot)
    await service.execute(subject, op, "synthetic message", ListingCardSearchRequest())
    async with pg[1].begin() as conn:
        await conn.execute(update(AISearchSession).values(expires_at=func.clock_timestamp() - timedelta(days=2)))
        await conn.execute(update(AISearchRequest).values(completed_at=func.clock_timestamp() - timedelta(days=31)))
    counts = await AIRetention(store).prune()
    assert counts.sessions == counts.results == counts.requests == 1
    with pytest.raises(SessionError, match="SESSION_NOT_FOUND"):
        await service.execute(subject, op, "synthetic message", ListingCardSearchRequest())
    assert parser.calls == 1
    async with pg[1]() as conn:
        assert await conn.scalar(select(func.count()).select_from(AISearchRequest)) == 0


async def test_gc_preserves_pending_and_skips_locked_rows(store, pg):
    subject = QuotaSubject(kind="auth", id=uuid4())
    pending, locked, _discard = [await store.create(subject) for _ in range(3)]
    op = operation(pending)
    await store.ledger.reserve(subject, op)
    async with pg[1].begin() as conn:
        await conn.execute(update(AISearchSession).values(expires_at=func.clock_timestamp() - timedelta(days=2)))
    async with pg[1].begin() as blocker:
        await blocker.execute(select(AISearchSession).where(AISearchSession.id == locked.intent.session_id).with_for_update())
        assert (await AIRetention(store).prune()).sessions == 1
    assert (await AIRetention(store).prune()).sessions == 1
    async with pg[1]() as conn:
        assert list(await conn.scalars(select(AISearchSession.id))) == [pending.intent.session_id]
        assert await conn.scalar(select(func.count()).select_from(AISearchRequest)) == 1


async def test_abandoned_seed_uses_created_age_and_preserves_edited_seed(store, pg):
    owner = QuotaSubject(kind="auth", id=uuid4())
    empty, edited = await store.create(owner), await store.create(owner)
    async with pg[1].begin() as conn:
        await conn.execute(update(AISearchSession).values(created_at=func.clock_timestamp() - timedelta(hours=2)))
        await conn.execute(update(AISearchSession).where(AISearchSession.id == edited.intent.session_id)
            .values(criteria={"balcony": {"strength": "hard", "value": True}}))
    assert (await AIRetention(store).prune(batch_size=1)).sessions == 1
    with pytest.raises(SessionError, match="SESSION_NOT_FOUND"):
        await store.get(owner, empty.intent.session_id)
    assert (await store.get(owner, edited.intent.session_id)).intent.criteria.balcony.value


async def test_new_invalid_session_is_rejected_before_quota_and_provider(store, pg):
    subject, snapshot, parser, gate, _query, service = await configured(store)
    async with pg[1].begin() as conn:
        await conn.execute(update(AISearchSession).values(created_at=func.clock_timestamp() - timedelta(days=8)))
    with pytest.raises(SessionError, match="SESSION_EXPIRED"):
        await service.execute(subject, operation(snapshot), "synthetic message", ListingCardSearchRequest())
    assert parser.calls == gate.calls == 0
    async with pg[1]() as conn:
        assert await conn.scalar(select(func.count()).select_from(AISearchRequest)) == 0
        assert await conn.scalar(select(func.count()).select_from(AIUsageDay)) == 0


async def test_own_text_deadline_bounds_hanging_parser_and_recovers_without_debit(store, pg):
    subject, snapshot, parser, gate, query, _service = await configured(store)
    parser.finish = asyncio.Event()
    service = TextSearchExecution(store, parser, gate, query, total_budget_seconds=.1)
    op = operation(snapshot)
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(service.execute(subject, op, "synthetic message", ListingCardSearchRequest()), 1)
    assert parser.calls == 1 and query.calls == 0
    # The exhausted deadline cannot start unbounded release. Recovery owns it.
    async with pg[1].begin() as conn:
        await conn.execute(update(AISearchRequest).values(lease_until=func.clock_timestamp() - timedelta(seconds=2),
            recover_after=func.clock_timestamp() - timedelta(seconds=1)))
    recovered = await store.ledger.recover_expired()
    assert len(recovered) == 1 and recovered[0].failure_code == "LEASE_EXPIRED"
    assert await usage(pg, subject) == (0, 0)
    retry = await service.execute(subject, op, "synthetic message", ListingCardSearchRequest())
    assert retry.replay and retry.operation.status == "failed" and parser.calls == 1


def test_absolute_policy_rejects_unbounded_lifetime():
    with pytest.raises(ValueError):
        SessionPolicy(inactivity_seconds=86400, absolute_seconds=604801)


async def test_recovery_tolerates_concurrent_explicit_erasure(store, pg, monkeypatch):
    owner = QuotaSubject(kind="auth", id=uuid4())
    initial = await store.create(owner)
    op = operation(initial)
    await store.ledger.reserve(owner, op)
    async with pg[1].begin() as conn:
        await conn.execute(update(AISearchRequest).values(lease_until=func.clock_timestamp() - timedelta(seconds=2),
            recover_after=func.clock_timestamp() - timedelta(seconds=1)))
    recover = store.ledger.recover
    async def erase_then_recover(subject, key):
        async with pg[1].begin() as conn:
            await conn.execute(delete(AISearchRequest))
            await conn.execute(update(AIUsageDay).values(reserved=0))
        return await recover(subject, key)
    monkeypatch.setattr(store.ledger, "recover", erase_then_recover)
    assert await store.ledger.recover_expired() == []
    assert await usage(pg, owner) == (0, 0)


async def test_explicit_close_frees_session_capacity_without_resetting_quota(store, pg):
    owner = QuotaSubject(kind="guest", id=uuid4())
    initial = await store.create(owner, max_active=1)
    _, receipt, _ = await complete(store, owner, initial, {"balcony": {"strength": "hard", "value": True}})
    with pytest.raises(SessionError, match="SESSION_VERSION_CONFLICT"):
        await store.close(owner, initial.intent.session_id, 0)
    await store.close(owner, initial.intent.session_id, 1)
    await store.close(owner, initial.intent.session_id, 1)  # idempotent close
    new = await store.create(owner, max_active=1)
    assert new.intent.session_id != initial.intent.session_id
    assert await usage(pg, owner) == (1, 0)
    with pytest.raises(SessionError, match="RESULT_EXPIRED_REQUERY_REQUIRED"):
        await store.result(owner, receipt.result_ref)


async def test_clarification_is_terminal_replayable_and_free_without_partial_intent(store, pg):
    from unittest.mock import AsyncMock
    subject, snapshot, parser, gate, query, service = await configured(store)
    parser.parse = AsyncMock(return_value=IntentClarification(reason="budget_period"))
    op = operation(snapshot)
    first = await service.execute(subject, op, "synthetic message", ListingCardSearchRequest())
    assert first.clarification.reason == "budget_period" and first.operation.status == "failed"
    assert first.operation.failure_code == "CLARIFY_BUDGET_PERIOD"
    assert first.cards is None and query.calls == 0 and await usage(pg, subject) == (0, 0)
    replay = await service.execute(subject, op, "synthetic message", ListingCardSearchRequest())
    assert replay.replay and replay.clarification == first.clarification
    assert parser.parse.await_count == gate.calls == 1
    assert await store.get(subject, snapshot.intent.session_id) == snapshot


async def test_corrected_full_request_binds_question_owner_session_and_version(store, pg):
    from unittest.mock import AsyncMock
    subject, snapshot, parser, _gate, query, service = await configured(store)
    original_parse = parser.parse
    parser.parse = AsyncMock(return_value=IntentClarification(reason="rental_mode"))
    question = operation(snapshot)
    await service.execute(subject, question, "synthetic message", ListingCardSearchRequest())
    parser.parse = original_parse
    wrong = operation(snapshot).model_copy(update={"clarification_key": uuid4()})
    with pytest.raises(SessionError, match="SESSION_STATE_INVALID"):
        await service.execute(subject, wrong, "synthetic message", ListingCardSearchRequest())
    other = await store.create(subject)
    wrong = operation(other).model_copy(update={"clarification_key": question.idempotency_key})
    with pytest.raises(SessionError, match="SESSION_STATE_INVALID"):
        await service.execute(subject, wrong, "synthetic message", ListingCardSearchRequest())
    answer = operation(snapshot).model_copy(update={"clarification_key": question.idempotency_key})
    completed = await service.execute(subject, answer, "synthetic message", ListingCardSearchRequest())
    assert completed.operation.status == "succeeded" and completed.clarification is None
    assert await usage(pg, subject) == (1, 0) and query.calls == 1
    # Reusing the old question with a newer intent is not a valid clarification.
    next_session = await store.get(subject, snapshot.intent.session_id)
    wrong = operation(next_session).model_copy(update={"clarification_key": question.idempotency_key})
    with pytest.raises(SessionError, match="SESSION_STATE_INVALID"):
        await service.execute(subject, wrong, "synthetic message", ListingCardSearchRequest())
