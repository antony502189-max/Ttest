"""Site-domain pilot, initially locked. An explicit approval artifact opens IO."""
import hashlib
import json
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from pydantic import SecretStr
from sqlalchemy.engine import make_url

from app.services.ai_closed_deepseek import _BudgetTransport
from app.services.ai_decision_intent import DecisionDeepSeekIntent
from app.services.ai_deepseek_intent import DeepSeekPolicy, ProviderFailure
from demo.entry import pipeline
from pilot.budget import ATTEMPT, BINDING, PilotBudget
from pilot.input import PilotGate, minimize, safe_criteria, validate_result

ORIGIN = "https://app.112233.es"
STATE = Path("/demo-state")


def require_pilot():
    expected = {"APP_ENV": "test", "AI_SITE_PILOT": "site-pilot-20261108.v1",
        "REDIS_URL": "redis://redis:6379/0", "FRONTEND_APP_URL": ORIGIN,
        "FRONTEND_ORIGINS": ORIGIN, "EXTERNAL_IMPORT_ENABLED": "false", "EXTERNAL_REMOVAL_CHECK_ENABLED": "false"}
    url = make_url(os.environ.get("DATABASE_URL", ""))
    if (any(os.environ.get(k) != v for k, v in expected.items())
            or url.drivername != "postgresql+asyncpg" or url.host != "postgres"
            or url.username != "ai_demo" or url.database != "ai_text_demo_20261108"
            or not re.fullmatch(r"[0-9a-f]{64}", url.password or "") or url.query):
        raise ValueError("ISOLATED_SITE_PILOT_CONFIGURATION_REQUIRED")


def approved():
    path = Path("/pilot-control/approval.json")
    if not path.exists():
        return False
    value = json.loads(path.read_bytes())
    if value != {"binding": BINDING, "owner_approved": True, "max_calls": 50,
                 "max_micro_usd": 1_000_000, "scope": "owner-team-nonpersonal-positive-rent-grammar.v1"}:
        raise ValueError("PILOT_APPROVAL_MISMATCH")
    return True


class PilotParser(DecisionDeepSeekIntent):
    def __init__(self, budget):
        self.budget, self.gate = budget, PilotGate()
        self.policy = DeepSeekPolicy(model="deepseek-flash", timeout_seconds=8,
            total_budget_seconds=10, max_tokens=1024, max_attempts=1,
            retry_delay_seconds=0, max_response_bytes=65536)

    async def parse(self, text, current):
        canonical = minimize(text)
        safe_criteria(current.criteria)
        if not approved():
            raise ProviderFailure("PILOT_SPENDING_APPROVAL_REQUIRED")
        key = Path("/pilot-control/deepseek.env").read_text().strip()
        prefix = "AI_INTENT_EVAL_DEEPSEEK_KEY="
        if not key.startswith(prefix) or "\n" in key or not key[len(prefix):]:
            raise ProviderFailure("DEDICATED_PILOT_KEY_REQUIRED")
        # Per-operation adapter: shared parser state cannot swap a concurrent
        # operation's transport while its gate is awaiting.
        adapter = object.__new__(DecisionDeepSeekIntent)
        adapter.key, adapter.gate, adapter.policy = SecretStr(key[len(prefix):]), self.gate, self.policy
        adapter.transport = _BudgetTransport(httpx.AsyncHTTPTransport(retries=0, trust_env=False,
            proxy="http://egress:3128", limits=httpx.Limits(max_connections=1, max_keepalive_connections=0)), self.budget)
        identity = hashlib.sha256(f"{current.session_id}|{current.version}|{canonical}".encode()).hexdigest()
        token = ATTEMPT.set(identity)
        try:
            patch = await adapter.parse(text, current)
            # Model output must implement exactly the bounded request; even a
            # schema-valid different budget cannot silently reach SQL.
            validate_result(current, patch, canonical)
            return patch
        finally:
            ATTEMPT.reset(token)


def create_app():
    require_pilot()
    from app.db.session import SessionLocal
    from app.main import app
    from app.repositories.ai_search_sessions import SessionPolicy
    from app.schemas.ai_search_quota import LeasePolicy
    from app.services.ai_guest_tokens import GuestPolicy, GuestTokens
    from app.services.ai_http_policy import AIHTTPPolicy
    from app.services.ai_text_runtime import assemble_text_runtime, install_text_runtime
    from app.services.rate_limit import RedisRateLimiter
    from demo.seed_state import verify_completed
    keys = json.loads((STATE / "signing.json").read_bytes())
    budget = PilotBudget(STATE / "provider.sqlite3")
    runtime = assemble_text_runtime(pipeline=pipeline(SessionLocal), parser=PilotParser(budget),
        limiter=RedisRateLimiter("redis://redis:6379/0"),
        lease_policy=LeasePolicy(reservation_seconds=60, running_seconds=60, recovery_grace_seconds=30),
        session_policy=SessionPolicy(inactivity_seconds=86400),
        guests=GuestTokens(key=bytes.fromhex(keys["guest"]), policy=GuestPolicy(ttl_seconds=604800)),
        cursor_key=bytes.fromhex(keys["cursor"]), http_policy=AIHTTPPolicy(20, 3, (), ORIGIN),
        origins=frozenset({ORIGIN}), max_body_bytes=32768, execution_seconds=15)
    install_text_runtime(app, runtime)
    original = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        await verify_completed(SessionLocal, keys)
        async with original(application):
            yield
    app.router.lifespan_context = lifespan

    @app.get("/api/v1/private-demo/status", include_in_schema=False)
    async def status():
        import asyncio

        from fastapi.responses import JSONResponse
        value = await asyncio.to_thread(budget.status)
        value["approved"] = approved()
        value["halted"] = value["halted"] or not value["approved"]
        return JSONResponse(value, headers={"Cache-Control": "no-store"})
    return app
