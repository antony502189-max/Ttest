"""Mock HTTP provider through real session/CAS/quota transactions; no network."""
import asyncio
import json
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import update
from test_execution import Gate, Query, operation
from test_sessions import usage

from app.models.ai_search_session import AISearchSession
from app.schemas.ai_search_quota import QuotaSubject
from app.schemas.listings import ListingCardSearchRequest
from app.services.ai_deepseek_intent import DeepSeekPolicy, OfflineDeepSeekIntent, OutboundIntentInput
from app.services.ai_search_execution import TextSearchExecution

pytestmark = pytest.mark.integration


class OutboundGate:
    async def prepare(self, text, state):
        return OutboundIntentInput(schema_version="ai-intent-input.v1", provider="deepseek", purpose="intent_patch",
                                   text="synthetic minimized search", criteria=state.criteria)


def parser(handler, *, budget=1.0):
    return OfflineDeepSeekIntent(transport=httpx.MockTransport(handler), key=SecretStr("synthetic-offline-key"),
        policy=DeepSeekPolicy(model="deepseek-flash", timeout_seconds=.5, total_budget_seconds=budget,
                              max_tokens=512, max_attempts=2, retry_delay_seconds=0.0, max_response_bytes=4096),
        gate=OutboundGate())


@pytest.mark.parametrize("case", ["empty", "same", "absent_remove", "pets", "amenities", "deadline", "changed"])
async def test_real_provider_boundary_preserves_intent_quota_and_replay(store, pg, case):
    subject = QuotaSubject(kind="guest", id=uuid4())
    snapshot = await store.create(subject)
    initial = {"balcony": {"strength": "hard", "value": True}} if case == "same" else {}
    if case in {"pets", "amenities"}:
        initial = {case: {"strength": "hard", "value": [
            {"species": "dog", "size": "small", "count": 1}] if case == "pets" else ["wifi"]}}
    async with pg[1]() as session, session.begin():
        await session.execute(update(AISearchSession).where(AISearchSession.id == snapshot.intent.session_id).values(criteria=initial))
    calls, closed = [], []
    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(100):
                await asyncio.sleep(.02)
                yield b" "
        async def aclose(self):
            closed.append(True)
    def handler(request):
        calls.append(request)
        if case == "deadline":
            return httpx.Response(200, stream=SlowStream())
        change = {"set": {}, "remove": []}
        if case in {"same", "changed"}:
            change["set"] = {"balcony": {"strength": "hard", "value": True}}
        elif case in {"pets", "amenities"}:
            change["set"] = {case: {"strength": "hard", "value": []}}
        elif case == "absent_remove":
            change["remove"] = ["pets"]
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "role": "assistant", "content": json.dumps(change)}}]})
    query, gate = Query(store), Gate()
    query.total = 0  # A real change with zero matches is still one successful search.
    service = TextSearchExecution(store, parser(handler, budget=.05 if case == "deadline" else 1.0), gate, query)
    op = operation(snapshot)
    first = await service.execute(subject, op, "synthetic message", ListingCardSearchRequest())
    replay = await service.execute(subject, op, "synthetic message", ListingCardSearchRequest())
    actual = (await store.get(subject, snapshot.intent.session_id)).intent
    assert len(calls) == gate.calls == 1 and replay.replay
    if case == "changed":
        assert first.operation.status == "succeeded" and first.operation.receipt.count == 0
        assert replay.operation.receipt == first.operation.receipt
        assert await usage(pg, subject) == (1, 0)
        assert actual.version == 1 and actual.criteria.balcony.value
        assert query.calls == query.replays == 1
    else:
        assert first.operation.status == "failed" and first.operation.failure_code == "LLM_FAILURE"
        assert first.operation.receipt is None and replay.cards is None
        assert await usage(pg, subject) == (0, 0)
        assert actual.version == 0 and actual.criteria.model_dump(mode="json", exclude_none=True) == initial
        assert query.calls == query.replays == 0
    if case == "deadline":
        assert closed == [True]


@pytest.mark.parametrize("budget,allowed", [(.5, True), (1.0, False), (2.0, False)])
def test_provider_deadline_must_leave_running_lease_headroom(store, budget, allowed):
    store.ledger.policy = store.ledger.policy.model_copy(update={"running_seconds": 1})
    provider = parser(lambda request: pytest.fail("no HTTP during configuration"), budget=budget)
    if allowed:
        TextSearchExecution(store, provider, Gate(), Query(store))
    else:
        with pytest.raises(ValueError, match="parser deadline must be shorter than running lease"):
            TextSearchExecution(store, provider, Gate(), Query(store))
