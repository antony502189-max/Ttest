"""Real PG quota/session transactions with offline parser and query fakes."""
import asyncio
import hashlib
import json
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from test_sessions import usage

from app.models.ai_search_quota import AIUsageDay
from app.repositories.ai_search_quota import QuotaError
from app.repositories.ai_search_sessions import intent_hash
from app.repositories.ai_verified_cards import VerifiedCardResult
from app.schemas.ai_search_intent import IntentPatch
from app.schemas.ai_search_quota import QuotaOperation, QuotaSubject
from app.schemas.listings import ListingCardSearchRequest, ListingCardSearchResponse
from app.services.ai_search_attempts import AIAttemptRejected
from app.services.ai_search_execution import TextSearchExecution

pytestmark = pytest.mark.integration


class Parser:
    def __init__(self):
        self.calls = 0
        self.changes = {"furnished": {"strength": "hard", "value": True}}
        self.error = None
        self.started, self.finish = asyncio.Event(), None

    async def parse(self, message, current):
        self.calls += 1
        self.started.set()
        if self.finish:
            await self.finish.wait()
        if self.error:
            raise self.error
        return IntentPatch.model_validate_json(json.dumps({"schema_version": "ai-search.v1",
            "session_id": str(current.session_id), "expected_version": current.version, "set": self.changes}))


class Gate:
    def __init__(self):
        self.calls, self.error = 0, None

    async def check(self, subject):
        self.calls += 1
        if self.error:
            raise self.error


class Query:
    def __init__(self, store):
        self.store, self.calls, self.replays = store, 0, 0
        self.total, self.error = 3, None
        self.started, self.finish = asyncio.Event(), None

    def result(self, intent):
        return VerifiedCardResult(ListingCardSearchResponse(items=[], total=self.total,
            nextCursor=None, previousCursor=None), intent_hash(intent), ())

    async def query_candidate(self, subject, current, candidate, payload):
        self.calls += 1
        self.started.set()
        if self.finish:
            await self.finish.wait()
        if self.error:
            raise self.error
        return self.result(candidate)

    async def query_result(self, subject, result_ref, payload):
        self.replays += 1
        return self.result((await self.store.result(subject, result_ref)).intent)


async def configured(store):
    subject = QuotaSubject(kind="guest", id=uuid4())
    snapshot = await store.create(subject)
    parser, gate, query = Parser(), Gate(), Query(store)
    service = TextSearchExecution(store, parser, gate, query)
    return subject, snapshot, parser, gate, query, service


def operation(snapshot, message="synthetic message"):
    return QuotaOperation(idempotency_key=uuid4(), channel="text", payload_sha256=hashlib.sha256(message.encode()).hexdigest(),
        session_id=snapshot.intent.session_id, expected_session_version=snapshot.intent.version)


@pytest.mark.parametrize("total", [0, 3])
async def test_success_and_replay_one_debit_one_parser_even_for_zero(store, pg, total):
    subject, snapshot, parser, gate, query, service = await configured(store)
    query.total = total
    op = operation(snapshot)
    first = await service.execute(subject, op, "synthetic message", ListingCardSearchRequest())
    assert first.operation.status == "succeeded" and first.operation.receipt.count == total
    assert first.cards.cards.total == total and await usage(pg, subject) == (1, 0)
    query.total = total + 1
    replay = await service.execute(subject, op, "synthetic message", ListingCardSearchRequest())
    assert replay.replay and replay.operation.receipt == first.operation.receipt
    assert replay.cards.cards.total == total + 1  # current verified cards, durable original count unchanged
    assert parser.calls == gate.calls == query.calls == query.replays == 1
    assert await usage(pg, subject) == (1, 0)
    assert (await store.get(subject, op.session_id)).intent.version == 1


async def test_inflight_duplicate_does_not_invoke_parser_twice(store, pg):
    subject, snapshot, parser, gate, _query, service = await configured(store)
    parser.finish = asyncio.Event()
    op = operation(snapshot)
    running = asyncio.create_task(service.execute(subject, op, "synthetic message", ListingCardSearchRequest()))
    await parser.started.wait()
    duplicate = await service.execute(subject, op, "synthetic message", ListingCardSearchRequest())
    assert duplicate.operation.status == "running" and duplicate.cards is None
    assert parser.calls == gate.calls == 1
    parser.finish.set()
    assert (await running).operation.status == "succeeded"
    assert await usage(pg, subject) == (1, 0)


@pytest.mark.parametrize("failure", ["parser", "gate", "query", "invalid_patch", "owner", "version"])
async def test_failure_has_no_debit_or_session_mutation(store, pg, failure):
    subject, snapshot, parser, gate, query, service = await configured(store)
    owner = subject
    if failure == "parser":
        parser.error = RuntimeError("PRIVATE_SYNTHETIC_PROVIDER_ERROR")
    elif failure == "gate":
        gate.error = AIAttemptRejected("ABUSE_GATE_UNAVAILABLE")
    elif failure == "query":
        query.error = RuntimeError("PRIVATE_SYNTHETIC_SQL_ERROR")
    elif failure == "invalid_patch":
        parser.changes = {"invented": {"strength": "hard", "value": True}}
    elif failure == "owner":
        subject = QuotaSubject(kind="guest", id=uuid4())
    op = operation(snapshot)
    if failure == "version":
        op = op.model_copy(update={"expected_session_version": 1})
    result = await service.execute(subject, op, "synthetic message", ListingCardSearchRequest())
    assert result.operation.status == "failed" and result.cards is None
    assert await usage(pg, subject) == (0, 0)
    retry = await service.execute(subject, op, "synthetic message", ListingCardSearchRequest())
    assert retry.replay and retry.operation.failure_code == result.operation.failure_code
    assert (await store.get(owner, op.session_id)).intent.version == 0
    assert "PRIVATE" not in str(result.operation.model_dump())


async def test_two_operations_same_version_only_one_cas_and_debit(store, pg):
    subject, snapshot, _parser, _gate, query, service = await configured(store)
    query.finish = asyncio.Event()
    first = asyncio.create_task(service.execute(subject, operation(snapshot), "synthetic message", ListingCardSearchRequest()))
    await query.started.wait()
    query.started.clear()
    second = asyncio.create_task(service.execute(subject, operation(snapshot), "synthetic message", ListingCardSearchRequest()))
    await query.started.wait()
    query.finish.set()
    results = await asyncio.gather(first, second)
    assert sorted(result.operation.status for result in results) == ["failed", "succeeded"]
    assert await usage(pg, subject) == (1, 0)
    assert (await store.get(subject, snapshot.intent.session_id)).intent.version == 1


async def test_cancel_during_parser_releases_without_debit(store, pg):
    subject, snapshot, parser, _, _, service = await configured(store)
    parser.finish = asyncio.Event()
    task = asyncio.create_task(service.execute(subject, operation(snapshot), "synthetic message", ListingCardSearchRequest()))
    await parser.started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await usage(pg, subject) == (0, 0)
    assert (await store.get(subject, snapshot.intent.session_id)).intent.version == 0


async def test_commit_ack_failure_replays_success_without_second_parser_or_debit(store, pg, monkeypatch):
    subject, snapshot, parser, _, query, service = await configured(store)
    original = store.finalize_patch
    async def lost_ack(*args, **kwargs):
        await original(*args, **kwargs)
        raise OSError("SYNTHETIC_ACK_LOST")
    monkeypatch.setattr(store, "finalize_patch", lost_ack)
    op = operation(snapshot)
    with pytest.raises(OSError):
        await service.execute(subject, op, "synthetic message", ListingCardSearchRequest())
    assert await usage(pg, subject) == (1, 0)
    retry = await service.execute(subject, op, "synthetic message", ListingCardSearchRequest())
    assert retry.replay and retry.operation.status == "succeeded"
    assert parser.calls == query.calls == 1 and query.replays == 1
    assert await usage(pg, subject) == (1, 0)


async def test_old_result_replay_preserves_original_intent_after_followup(store, pg):
    subject, snapshot, parser, _, _, service = await configured(store)
    op = operation(snapshot)
    first = await service.execute(subject, op, "synthetic message", ListingCardSearchRequest())
    current = await store.get(subject, snapshot.intent.session_id)
    parser.changes = {"balcony": {"strength": "hard", "value": True}}
    second = await service.execute(subject, operation(current), "synthetic message", ListingCardSearchRequest())
    assert second.operation.status == "succeeded"
    state = (await store.get(subject, snapshot.intent.session_id)).intent
    assert state.criteria.furnished.value and state.criteria.balcony.value
    retry = await service.execute(subject, op, "synthetic message", ListingCardSearchRequest())
    assert retry.cards.intent_hash == first.cards.intent_hash != second.cards.intent_hash
    assert parser.calls == 2 and await usage(pg, subject) == (2, 0)


async def test_hash_mismatch_or_paging_cursor_rejected_before_reservation(store, pg):
    subject, snapshot, parser, gate, _, service = await configured(store)
    with pytest.raises(ValueError, match="hash"):
        await service.execute(subject, operation(snapshot), "different", ListingCardSearchRequest())
    with pytest.raises(ValueError, match="paging"):
        await service.execute(subject, operation(snapshot), "synthetic message", ListingCardSearchRequest(cursor="not-new-message"))
    assert parser.calls == gate.calls == 0
    async with pg[1]() as session:
        assert await session.scalar(select(func.count()).select_from(AIUsageDay)) == 0


@pytest.mark.parametrize("change", [
    {"rentalMode": "holiday"}, {"maxPrice": 500}, {"sort": "price_asc"},
    {"favoriteIds": [str(uuid4())]}, {"limit": 1},
])
async def test_same_idempotency_key_different_filters_conflicts(store, pg, change):
    subject, snapshot, parser, gate, query, service = await configured(store)
    op = operation(snapshot)
    first = await service.execute(subject, op, "synthetic message", ListingCardSearchRequest())
    assert first.operation.status == "succeeded"
    with pytest.raises(QuotaError, match="IDEMPOTENCY_CONFLICT"):
        await service.execute(subject, op, "synthetic message", ListingCardSearchRequest(**change))
    replay = await service.execute(subject, op, "synthetic message", ListingCardSearchRequest())
    assert replay.replay and replay.operation.receipt == first.operation.receipt
    assert parser.calls == gate.calls == query.calls == query.replays == 1
    assert await usage(pg, subject) == (1, 0)
