"""Offline model boundary; the real decision adapter handles all parsing.

These completions are test fixtures, never model-quality evidence. No outbound
network, provider key, eval journal or corpus approval is used by this mode.
"""
import asyncio
import json

import httpx
from pydantic import SecretStr

from app.schemas.ai_search_intent import Criteria, IntentPatch
from app.services.ai_decision_intent import DecisionDeepSeekIntent
from app.services.ai_deepseek_intent import DeepSeekPolicy, OutboundIntentInput, ProviderFailure


class LocalOnlyGate:
    async def prepare(self, text, current):
        return OutboundIntentInput(schema_version="ai-intent-input.v1", provider="deepseek",
                                   purpose="intent_patch", text=text, criteria=current.criteria)


def completion(text, criteria):
    # Exact fixtures deliberately do not pretend to understand arbitrary text.
    from copy import deepcopy

    from lab.decision_fixtures import FIXTURES
    if not criteria and text in FIXTURES:
        return {"status": "patch", "patch": {"set": deepcopy(FIXTURES[text]), "remove": []}}
    decisions = {"уточнить бюджет": "clarification", "ничего не менять": "no_change",
                 "рядом с хорошими людьми": "unsupported"}
    if text in decisions:
        return {"status": decisions[text], "patch": None}
    from lab.ai_text import SyntheticParser
    # Share finite fixture vocabulary, but only to generate provider bytes at
    # the model transport boundary. It never returns a patch to execution.
    return SyntheticParser, criteria


class ModelFixtureTransport(httpx.MockTransport):
    def __init__(self, redis):
        self.redis = redis
        # Context belongs to this parse call, not a shared mutable transport.
        super().__init__(self.handle)

    async def handle(self, request):
        if str(request.url) != "https://api.deepseek.com/chat/completions" or request.method != "POST":
            raise ProviderFailure("PROVIDER_DESTINATION_REJECTED")
        # Adapter strips identity. ContextVar supplies local test-control keys;
        # neither these keys nor IDs enter the model request.
        current = _current.get()
        key = f"lab-acceptance:{current.session_id}:{current.version}"
        await self.redis.incr(key + ":calls")
        await self.redis.expire(key + ":calls", 7200)
        fault = await self.redis.getdel(key + ":fault")
        if fault in {"delay", "timeout"}:
            await asyncio.sleep(3 if fault == "delay" else 18)
        elif fault == "cancel":
            raise asyncio.CancelledError
        elif fault == "failure":
            return httpx.Response(200, json={"invalid": "synthetic"})
        payload = json.loads(request.content)
        data = json.loads(payload["messages"][1]["content"])
        if set(data) != {"text", "criteria"}:
            raise AssertionError("unexpected outbound field")
        decision = completion(data["text"], data["criteria"])
        if isinstance(decision, tuple):
            parser, criteria = decision
            fixture_state = current.model_copy(update={"criteria": Criteria.model_validate_json(json.dumps(criteria))})
            try:
                patch: IntentPatch = await parser().parse(data["text"], fixture_state)
                decision = {"status": "patch", "patch": {"set": patch.set.model_dump(mode="json", exclude_none=True),
                                                            "remove": list(patch.remove)}}
            except ValueError:
                decision = {"status": "unsupported", "patch": None}
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "role": "assistant", "content": json.dumps(decision)}}]})


from contextvars import ContextVar

_current = ContextVar("local_model_fixture_state")


class LocalDecisionParser(DecisionDeepSeekIntent):
    def __init__(self, redis):
        super().__init__(transport=ModelFixtureTransport(redis), key=SecretStr("synthetic-local-only"),
            gate=LocalOnlyGate(), policy=DeepSeekPolicy(model="deepseek-flash", timeout_seconds=8,
                total_budget_seconds=10, max_tokens=1024, max_attempts=1, retry_delay_seconds=0,
                max_response_bytes=65536))

    async def parse(self, text, current):
        token = _current.set(current)
        try:
            return await super().parse(text, current)
        finally:
            _current.reset(token)
