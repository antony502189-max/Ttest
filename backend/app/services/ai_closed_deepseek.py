"""Explicit closed-evaluation provider. Never registered by app.main/settings.

Only the lab composition supplies a reviewed synthetic outbound gate. All HTTP
attempts reserve their full allowance durably BEFORE IO, including failures and
retries. A reservation is never refunded after ambiguous provider acknowledgement.
"""
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

import httpx
from pydantic import SecretStr

from .ai_decision_intent import DecisionDeepSeekIntent, IntentDecision  # noqa: F401 - compatibility export
from .ai_deepseek_intent import (
    DeepSeekPolicy,
    IntentOutboundGate,
    ProviderFailure,
    _strict_json,
)

APPROVAL = "deepseek-synthetic-intent-v1"
MAX_CALLS = 56  # Owner approved full regression after the first 27 cumulative attempts.
MAX_MICRO_USD = 750_000  # USD 0.75 cumulative; retain the SAME journal and old reservations.
INPUT_TOKEN_ALLOWANCE = 32_768
OUTPUT_TOKENS = 1024
# Peak cache-miss ceilings checked against official pricing on 2026-10-31:
# USD 0.30 / 1M input, USD 1.20 / 1M output. Never count cache/off-peak discounts.
RESERVE_MICRO_USD = (INPUT_TOKEN_ALLOWANCE * 3 + OUTPUT_TOKENS * 12 + 9) // 10
POLICY = DeepSeekPolicy(model="deepseek-flash", timeout_seconds=10.0, total_budget_seconds=25.0,
                        max_tokens=OUTPUT_TOKENS, max_attempts=2, retry_delay_seconds=0.5,
                        max_response_bytes=65_536)


class EvaluationBudget:
    """Small single-host journal. No text, credentials or response bodies.

    BEGIN IMMEDIATE fences competing processes. The immutable run/corpus binding
    prevents resetting counters by changing configuration at the same path.
    Retain this journal for resumed runs; a new file is a NEW spending approval.
    """
    def __init__(self, path: Path, *, corpus_sha256: str):
        self.path = Path(path)
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS binding (id INTEGER PRIMARY KEY CHECK(id=1), corpus TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO binding VALUES (1, ?)", (corpus_sha256,))
            if db.execute("SELECT corpus FROM binding WHERE id=1").fetchone() != (corpus_sha256,):
                raise ProviderFailure("EVALUATION_JOURNAL_MISMATCH")
            db.execute("CREATE TABLE IF NOT EXISTS attempts (id INTEGER PRIMARY KEY, reserved INTEGER NOT NULL, "
                       "prompt_tokens INTEGER, completion_tokens INTEGER)")

    @contextmanager
    def _connect(self):
        with closing(sqlite3.connect(self.path, timeout=1.0)) as db, db:
            yield db

    def reserve(self) -> int:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            calls, spent = db.execute("SELECT count(*), coalesce(sum(reserved),0) FROM attempts").fetchone()
            if calls >= MAX_CALLS or spent + RESERVE_MICRO_USD > MAX_MICRO_USD:
                raise ProviderFailure("PROVIDER_COST_BUDGET_EXHAUSTED")
            result = db.execute("INSERT INTO attempts(reserved) VALUES (?)", (RESERVE_MICRO_USD,))
            return result.lastrowid

    def record_usage(self, ticket: int, data: bytes):
        try:
            envelope = _strict_json(data)
            usage = envelope["usage"]
            prompt, completion = usage["prompt_tokens"], usage["completion_tokens"]
            if type(prompt) is not int or type(completion) is not int or prompt < 1 or completion < 0:
                raise ValueError("invalid usage")
            if prompt > INPUT_TOKEN_ALLOWANCE or completion > OUTPUT_TOKENS:
                # Poison remaining budget rather than silently allowing further IO.
                with self._connect() as db:
                    db.execute("UPDATE attempts SET reserved=? WHERE id=?", (MAX_MICRO_USD, ticket))
                raise ProviderFailure("PROVIDER_USAGE_ALLOWANCE_EXCEEDED")
            if type(usage.get("total_tokens")) is not int or usage["total_tokens"] != prompt + completion:
                raise ValueError("usage mismatch")
            with self._connect() as db:
                db.execute("UPDATE attempts SET prompt_tokens=?, completion_tokens=? WHERE id=?",
                           (prompt, completion, ticket))
        except ProviderFailure:
            raise
        except (KeyError, TypeError, ValueError, UnicodeError, RecursionError):
            raise ProviderFailure("PROVIDER_USAGE_INVALID") from None

    def summary(self) -> dict:
        with self._connect() as db:
            calls, reserved, observed, prompt, completion = db.execute(
                "SELECT count(*), coalesce(sum(reserved),0), count(prompt_tokens), "
                "coalesce(sum(prompt_tokens),0), coalesce(sum(completion_tokens),0) FROM attempts").fetchone()
        return {"attempts": calls, "reserved_micro_usd": reserved, "observed_usage_attempts": observed,
                "prompt_tokens": prompt, "completion_tokens": completion,
                "observed_peak_micro_usd": (prompt * 3 + completion * 12 + 9) // 10}


class _MeteredStream(httpx.AsyncByteStream):
    def __init__(self, inner, budget, ticket, limit):
        self.inner, self.budget, self.ticket, self.limit = inner, budget, ticket, limit

    async def __aiter__(self):
        data = bytearray()
        async for chunk in self.inner:
            if len(data) + len(chunk) > self.limit:
                raise ProviderFailure("PROVIDER_RESPONSE_TOO_LARGE")
            data.extend(chunk)
            yield chunk
        self.budget.record_usage(self.ticket, bytes(data))

    async def aclose(self):
        await self.inner.aclose()


class _BudgetTransport(httpx.AsyncBaseTransport):
    def __init__(self, inner, budget):
        self.inner, self.budget = inner, budget

    async def handle_async_request(self, request):
        if request.method != "POST" or str(request.url) != "https://api.deepseek.com/chat/completions":
            raise ProviderFailure("PROVIDER_DESTINATION_REJECTED")
        payload = _strict_json(request.content)
        # Conservative admission estimate: UTF-8 bytes plus message framing, with
        # 2x headroom. This is NOT a contractual provider tokenizer/billing cap.
        # Verify returned usage and stop on breach; use a dedicated funded key.
        size = sum(len(message["content"].encode()) for message in payload["messages"]) + 256
        if size * 2 > INPUT_TOKEN_ALLOWANCE:
            raise ProviderFailure("PROVIDER_INPUT_ALLOWANCE_EXCEEDED")
        if payload["model"] != POLICY.model or payload["max_tokens"] != OUTPUT_TOKENS:
            raise ProviderFailure("PROVIDER_POLICY_MISMATCH")
        ticket = self.budget.reserve()
        response = await self.inner.handle_async_request(request)
        if response.status_code == 200:
            # MockTransport fixtures may be buffered; real HTTP transport streams.
            if response.is_stream_consumed:
                if len(response.content) > POLICY.max_response_bytes:
                    raise ProviderFailure("PROVIDER_RESPONSE_TOO_LARGE")
                self.budget.record_usage(ticket, response.content)
            elif response.headers.get("content-encoding", "identity").strip().lower() == "identity":
                response.stream = _MeteredStream(response.stream, self.budget, ticket, POLICY.max_response_bytes)
        return response

    async def aclose(self):
        await self.inner.aclose()


class ClosedDeepSeekIntent(DecisionDeepSeekIntent):
    """Parser protocol compatible, but only explicitly composed in the lab CLI.

    Do not install in the synthetic UI lab: that lab has an offline-only network
    and forbids live credentials. No production activation switch is added.
    """
    def __init__(self, *, key: SecretStr, gate: IntentOutboundGate, budget: EvaluationBudget, approval: str):
        if approval != APPROVAL:
            raise ProviderFailure("LIVE_EVALUATION_APPROVAL_REQUIRED")
        if not isinstance(key, SecretStr) or not key.get_secret_value():
            raise ProviderFailure("DEDICATED_TEST_KEY_REQUIRED")
        self.key, self.gate, self.policy = key, gate, POLICY
        self.transport = _BudgetTransport(httpx.AsyncHTTPTransport(retries=0, trust_env=False,
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=0)), budget)
