"""08.11 owner approval: three exact rental phrases, <=$0.10 additional reserve.

Real provider and a small real public catalogue snapshot. No arbitrary input.
This separate journal never opens or changes the historical synthetic journal.
"""
import hashlib
import json
import logging
import os
import re
from contextlib import asynccontextmanager, suppress
from decimal import Decimal
from hmac import compare_digest
from pathlib import Path

import httpx
from pydantic import SecretStr
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from app.schemas.ai_search_intent import apply_patch
from app.services.ai_closed_deepseek import _BudgetTransport
from app.services.ai_decision_intent import DecisionDeepSeekIntent
from app.services.ai_deepseek_intent import DeepSeekPolicy, OutboundIntentInput, ProviderFailure
from demo.budget import ATTEMPT, TICKET, DemoBudget

ORIGIN = "http://localhost:9444"  # Loopback only, reached through an encrypted SSH tunnel.
APPROVAL = "owner-approved-private-text-demo-20261108-v1"
PHRASES = ("до 600 евро в месяц", "теперь до 400 евро в месяц", "убери ограничение бюджета")
BINDING = hashlib.sha256(json.dumps({"approval": APPROVAL, "phrases": PHRASES,
    "max_calls": 3, "max_micro_usd": 100000}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def require_demo():
    expected = {"APP_ENV": "test", "AI_PRIVATE_TEXT_DEMO_APPROVAL": APPROVAL,
        "REDIS_URL": "redis://redis:6379/0",
        "FRONTEND_APP_URL": ORIGIN, "FRONTEND_ORIGINS": ORIGIN,
        "EXTERNAL_IMPORT_ENABLED": "false", "EXTERNAL_REMOVAL_CHECK_ENABLED": "false"}
    if any(os.environ.get(k) != v for k, v in expected.items()):
        raise ValueError("PRIVATE_DEMO_CONFIGURATION_REQUIRED")
    try:
        url = make_url(os.environ.get("DATABASE_URL", ""))
        password = os.environ.get("AI_DEMO_DATABASE_PASSWORD", "")
        if (not re.fullmatch(r"[0-9a-f]{64}", password) or url.drivername != "postgresql+asyncpg"
                or url.username != "ai_demo" or url.host not in {"postgres", "127.0.0.1", "localhost"}
                or url.port not in {None, 5432} or url.database != "ai_text_demo_20261108"
                or not compare_digest(url.password or "", password) or url.query):
            raise ValueError
    except (ValueError, ArgumentError, UnicodeError):
        raise ValueError("PRIVATE_DEMO_DATABASE_CONFIGURATION_REQUIRED") from None


def approved_states():
    mode = {"rental_mode": {"strength": "hard", "value": "long"}}
    return [mode, *[mode | {"budget": {"strength": "hard", "value": {
        "amount": amount, "currency": "EUR", "period": "monthly"}}} for amount in ("600", "400")], mode]


def normalized_criteria(criteria):
    value = criteria.model_dump(mode="json", exclude_none=True)
    if "budget" in value:
        value["budget"]["value"]["amount"] = format(Decimal(value["budget"]["value"]["amount"]).normalize(), "f")
    return value


class DemoGate:
    async def prepare(self, text, current):
        # Check the exact sequential state; IDs/history/catalogue never enter IO.
        if text not in PHRASES or normalized_criteria(current.criteria) != approved_states()[PHRASES.index(text)]:
            raise ProviderFailure("PRIVATE_DEMO_INPUT_NOT_APPROVED")
        step = PHRASES.index(text)
        ATTEMPT.set((str(current.session_id), current.version, step))
        return OutboundIntentInput(schema_version="ai-intent-input.v1", provider="deepseek",
                                    purpose="intent_patch", text=text, criteria=current.criteria)


class DemoParser(DecisionDeepSeekIntent):
    def __init__(self):
        require_demo()
        self.budget = DemoBudget(Path("/demo-state/provider.sqlite3"), corpus_sha256=BINDING)
        # The key is mounted only in the private backend, never source/build/UI.
        # An exhausted demo can serve its durable results with NO mounted key.
        if self.budget.summary()["attempts"] >= 3:
            self.key = SecretStr("budget-exhausted-no-live-key")
        else:
            key = Path("/demo-secrets/deepseek.env").read_text(encoding="utf-8").strip()
            prefix = "AI_INTENT_EVAL_DEEPSEEK_KEY="
            if not key.startswith(prefix) or "\n" in key or not key[len(prefix):]:
                raise ValueError("DEDICATED_DEMO_KEY_REQUIRED")
            self.key = SecretStr(key[len(prefix):])
        self.gate = DemoGate()
        self.policy = DeepSeekPolicy(model="deepseek-flash", timeout_seconds=8,
            total_budget_seconds=10, max_tokens=1024, max_attempts=1,
            retry_delay_seconds=0, max_response_bytes=65536)
        self.transport = DemoTransport(httpx.AsyncHTTPTransport(retries=0, trust_env=False,
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=0)), self.budget)

    async def parse(self, text, current):
        attempt_context, ticket_context = ATTEMPT.set(None), TICKET.set(None)
        try:
            patch = await super().parse(text, current)
            attempt, ticket = ATTEMPT.get(), TICKET.get()
            if (attempt is None or ticket is None or normalized_criteria(apply_patch(current, patch).criteria)
                    != approved_states()[attempt[2] + 1]):
                raise ProviderFailure("PRIVATE_DEMO_SEMANTIC_SEQUENCE_REJECTED")
            self.budget.accept(ticket)
            return patch
        except BaseException:
            if TICKET.get() is not None:
                # An uncertain model/SQL continuation is never another paid
                # retry of step zero. Pending reservations also block restart.
                with suppress(Exception):
                    self.budget.uncertain(TICKET.get())
            raise
        finally:
            ATTEMPT.reset(attempt_context)
            TICKET.reset(ticket_context)


class DemoTransport(_BudgetTransport):
    async def handle_async_request(self, request):
        response = await super().handle_async_request(request)
        logging.getLogger(__name__).warning("private_demo_provider_status:%d", response.status_code)
        return response


def pipeline(factory):
    from app.repositories.ai_fact_pipeline import FactPipeline
    from app.schemas.ai_fact_pipeline import FactQueuePolicy
    from app.schemas.ai_listing_facts import FactVocabulary
    from app.services.ai_fact_quality import FactQualityPolicy
    return FactPipeline(factory, FactQueuePolicy(lease_seconds=60, max_attempts=2, retry_delay_seconds=1),
        FactVocabulary(amenity_codes=frozenset(), catalog_other_codes=frozenset(),
            tenant_group_codes=frozenset(), municipality_zones=frozenset()),
        resolver_version="private-pisocompartido.v1", operating_policy=FactQualityPolicy(
            price_max_age_seconds=86400, policy_max_age_seconds=86400, evidence_retention_seconds=86400))


def create_app():
    require_demo()
    from app.db.session import SessionLocal
    from app.main import app
    from app.repositories.ai_search_sessions import SessionPolicy
    from app.schemas.ai_search_quota import LeasePolicy
    from app.services.ai_guest_tokens import GuestPolicy, GuestTokens
    from app.services.ai_http_policy import AIHTTPPolicy
    from app.services.ai_text_runtime import assemble_text_runtime, install_text_runtime
    from app.services.rate_limit import RedisRateLimiter
    state = Path("/demo-state/signing.json")
    keys = json.loads(state.read_text())
    parser = DemoParser()
    runtime = assemble_text_runtime(pipeline=pipeline(SessionLocal), parser=parser,
        limiter=RedisRateLimiter("redis://redis:6379/0"),
        lease_policy=LeasePolicy(reservation_seconds=60, running_seconds=60, recovery_grace_seconds=30),
        session_policy=SessionPolicy(inactivity_seconds=86400),
        guests=GuestTokens(key=bytes.fromhex(keys["guest"]), policy=GuestPolicy(ttl_seconds=604800)),
        cursor_key=bytes.fromhex(keys["cursor"]), http_policy=AIHTTPPolicy(20, 3, (), ORIGIN),
        origins=frozenset({ORIGIN}), max_body_bytes=32768, execution_seconds=15)
    install_text_runtime(app, runtime)
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        if parser.budget.summary()["attempts"] < 3:
            from demo.seed import verify_completed
            await verify_completed(SessionLocal, keys)
        async with original_lifespan(application):
            yield

    app.router.lifespan_context = lifespan

    @app.get("/api/v1/private-demo/status", include_in_schema=False)
    async def demo_status():
        import asyncio

        from fastapi.responses import JSONResponse
        return JSONResponse(await asyncio.to_thread(parser.budget.status),
                            headers={"Cache-Control": "no-store"})
    return app
