"""Site-domain pilot, initially locked. An explicit approval artifact opens IO."""
import hashlib
import json
import os
import re
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import SecretStr
from sqlalchemy.engine import make_url

from app.repositories.ai_verified_cards import SourceCoverageUnavailable
from app.services.ai_closed_deepseek import _BudgetTransport
from app.services.ai_decision_intent import DecisionDeepSeekIntent
from app.services.ai_deepseek_intent import DeepSeekPolicy, ProviderFailure
from demo.entry import pipeline
from pilot.budget import ATTEMPT, BINDING, PilotBudget
from pilot.input import PilotGate, minimize, safe_criteria, validate_result
from pilot.readiness import CatalogReadiness
from pilot.surface import minimal_app

ORIGIN = "https://app.112233.es"
STATE = Path("/demo-state")
CONTROL = Path("/pilot-control")
# A separate, explicitly authorized one-day invitation beta. This does not
# reinterpret the existing owner/team artifact or create a fresh spend journal.
EXTERNAL_DEMO_END = datetime(2026, 11, 11, 20, 59, 59, tzinfo=UTC)


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
    path = CONTROL / "approval.json"
    if not path.exists():
        return False
    value = json.loads(path.read_bytes())
    common = {"binding": BINDING, "owner_approved": True, "max_calls": 50,
              "max_micro_usd": 1_000_000}
    if value == {**common, "scope": "owner-team-nonpersonal-positive-rent-grammar.v1"}:
        return True
    if value == {**common, "scope": "invited-external-nonpersonal-positive-rent-grammar.v1",
                 "max_invites": 10, "expires_at": "2026-11-11T20:59:59Z"}:
        return datetime.now(UTC) < EXTERNAL_DEMO_END
    raise ValueError("PILOT_APPROVAL_MISMATCH")


class PilotParser(DecisionDeepSeekIntent):
    def __init__(self, budget, readiness):
        self.budget, self.gate = budget, PilotGate()
        self.readiness = readiness
        self.policy = DeepSeekPolicy(model="deepseek-flash", timeout_seconds=8,
            total_budget_seconds=10, max_tokens=1024, max_attempts=1,
            retry_delay_seconds=0, max_response_bytes=65536)

    async def parse(self, text, current):
        canonical = minimize(text)
        safe_criteria(current.criteria)
        await require_catalog(self.readiness)
        if not approved():
            raise ProviderFailure("PILOT_SPENDING_APPROVAL_REQUIRED")
        key = (CONTROL / "deepseek.env").read_text().strip()
        prefix = "AI_INTENT_EVAL_DEEPSEEK_KEY="
        if not key.startswith(prefix) or "\n" in key or not key[len(prefix):]:
            raise ProviderFailure("DEDICATED_PILOT_KEY_REQUIRED")
        # Per-operation adapter: shared parser state cannot swap a concurrent
        # operation's transport while its gate is awaiting.
        adapter = object.__new__(DecisionDeepSeekIntent)
        adapter.key, adapter.gate, adapter.policy = SecretStr(key[len(prefix):]), self.gate, self.policy
        adapter.transport = PilotTransport(httpx.AsyncHTTPTransport(retries=0, trust_env=False,
            proxy="http://egress:3128", limits=httpx.Limits(max_connections=1, max_keepalive_connections=0)), self.budget, self.readiness)
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


async def require_catalog(readiness):
    if not (await readiness())["catalog_ready"]:
        raise SourceCoverageUnavailable("PILOT_CATALOG_STALE")


def require_approval():
    if not approved():
        raise ProviderFailure("PILOT_SPENDING_APPROVAL_REQUIRED")


class PilotTransport(_BudgetTransport):
    def __init__(self, inner, budget, readiness):
        super().__init__(inner, budget)
        self.readiness = readiness

    async def handle_async_request(self, request):
        await require_catalog(self.readiness)
        require_approval()
        return await super().handle_async_request(request)


def create_app():
    require_pilot()
    from app.db.session import SessionLocal
    app = minimal_app()
    from app.repositories.ai_search_sessions import SessionPolicy
    from app.schemas.ai_search_quota import LeasePolicy
    from app.services.ai_guest_tokens import GuestPolicy, GuestTokens
    from app.services.ai_http_policy import AIHTTPPolicy
    from app.services.ai_text_runtime import assemble_text_runtime, install_text_runtime
    from app.services.rate_limit import RedisRateLimiter
    from demo.seed_state import verify_completed
    keys = json.loads((STATE / "signing.json").read_bytes())
    budget = PilotBudget(STATE / "provider.sqlite3")
    budget.dispatch_guard = require_approval
    facts = pipeline(SessionLocal)
    from pilot.catalog_health import CatalogHealth, cohort_hash
    from pilot.guarded_cards import GuardedCards, install_catalog_guard
    health = CatalogHealth(STATE/'catalog-health.json',cohort_hash(json.loads(Path('/demo-input/catalog.json').read_text())))
    readiness = CatalogReadiness(facts,health)
    runtime = assemble_text_runtime(pipeline=facts, parser=PilotParser(budget, readiness),
        limiter=RedisRateLimiter("redis://redis:6379/0"),
        lease_policy=LeasePolicy(reservation_seconds=60, running_seconds=60, recovery_grace_seconds=30),
        session_policy=SessionPolicy(inactivity_seconds=86400),
        guests=GuestTokens(key=bytes.fromhex(keys["guest"]), policy=GuestPolicy(ttl_seconds=604800)),
        cursor_key=bytes.fromhex(keys["cursor"]), http_policy=AIHTTPPolicy(20, 3, ("172.30.41.2/32",), ORIGIN),
        origins=frozenset({ORIGIN}), max_body_bytes=32768, execution_seconds=15)
    guarded=GuardedCards(facts,runtime.sessions,signing_key=bytes.fromhex(keys['cursor']),health=health)
    runtime.execution.query=guarded
    runtime=replace(runtime,cards=guarded)
    install_catalog_guard(app,health)
    if os.environ.get("AI_SITE_PILOT_VOICE") == "local-pcm-v1":
        from app.services.ai_local_asr import LocalPCMTranscriber
        from app.services.ai_voice_execution import VoicePolicy, VoiceSearchExecution

        local_asr = LocalPCMTranscriber(python=Path("/opt/voice/bin/python"), model=Path("/opt/voice-model"))

        class ApprovedLocalASR:
            async def transcribe(self, audio, media_type):
                await require_catalog(readiness)
                require_approval()
                return await local_asr.transcribe(audio, media_type)

        runtime = replace(runtime, voice=VoiceSearchExecution(runtime.sessions, ApprovedLocalASR(),
            runtime.execution.parser, runtime.execution.attempts, runtime.cards,
            VoicePolicy(media_types=("audio/wav",), max_audio_bytes=480044, max_transcript_bytes=640,
                asr_budget_seconds=8.0, intent_budget_seconds=10.0, total_budget_seconds=19.0)))
    elif os.environ.get("AI_SITE_PILOT_VOICE"):
        raise ValueError("LOCAL_VOICE_CONFIGURATION_INVALID")
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
        try:
            value.update(await readiness())
        except Exception:  # noqa: BLE001 - fixed private fail-closed status
            value.update(catalog_ready=False, catalog_reason="PILOT_CATALOG_UNAVAILABLE")
        value["halted"] = value["halted"] or not value["approved"] or not value["catalog_ready"]
        return JSONResponse(value, headers={"Cache-Control": "no-store"})
    return app
