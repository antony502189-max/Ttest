"""Test-only composition root. Never imported by app.main or enabled by a key."""
import json
import os
from contextlib import asynccontextmanager

from redis.exceptions import RedisError
from sqlalchemy import text

ORIGIN = "https://localhost:9443"
DATABASE = "postgresql+asyncpg://ai_lab:synthetic-local-only@postgres:5432/ai_text_lab"
REDIS = "redis://redis:6379/0"
MARKER = "ttest-ai-text-lab.synthetic.v1"


def require_lab():
    # Exact dedicated destinations; no caller-supplied application DB/provider.
    expected = {"APP_ENV": "test", "AI_SYNTHETIC_LAB": MARKER,
                "DATABASE_URL": DATABASE, "REDIS_URL": REDIS,
                "FRONTEND_APP_URL": ORIGIN, "FRONTEND_ORIGINS": ORIGIN,
                "EXTERNAL_IMPORT_ENABLED": "false", "EXTERNAL_REMOVAL_CHECK_ENABLED": "false"}
    if any(os.environ.get(key) != value for key, value in expected.items()):
        raise RuntimeError("use only the dedicated ai-text-lab launcher/configuration")
    for name in ("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "SMTP_HOST", "SENTRY_DSN",
                 "GOOGLE_CLIENT_ID", "WEB_PUSH_PRIVATE_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY",
                 "AI_INTENT_EVAL_DEEPSEEK_KEY"):
        if os.environ.get(name):
            raise RuntimeError("real credentials/providers are forbidden in this synthetic lab")


async def verify_database(factory):
    async with factory() as connection:
        marker = await connection.scalar(text(
            "SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname=current_database()"))
        if marker != MARKER:
            raise RuntimeError("dedicated synthetic database marker missing")


def pipeline(factory):
    from app.repositories.ai_fact_pipeline import FactPipeline
    from app.schemas.ai_fact_pipeline import FactQueuePolicy
    from app.schemas.ai_listing_facts import FactVocabulary
    vocabulary = FactVocabulary(amenity_codes=frozenset(), catalog_other_codes=frozenset(),
                                tenant_group_codes=frozenset(), municipality_zones=frozenset())
    return FactPipeline(factory, FactQueuePolicy(lease_seconds=60, max_attempts=2, retry_delay_seconds=1),
                        vocabulary, resolver_version="synthetic-lab.v1")


class SyntheticParser:
    """Finite exact phrases, no model, transport, DNS, fuzzy interpretation or SQL."""

    async def parse(self, message, current):
        command = message.strip().casefold()
        changes, remove = {}, []
        if command == "все варианты":
            remove = [name for name in current.criteria.model_fields_set if name != "rental_mode"]
        elif command == "с маленькой собакой":
            changes = {"pets": {"strength": "hard", "value": [
                {"species": "dog", "size": "small", "count": 1}]}}
        elif command in {"до 600 евро в месяц", "до 400 евро в месяц"}:
            changes = {"budget": {"strength": "hard", "value": {
                "amount": "600" if "600" in command else "400", "currency": "EUR", "period": "monthly"}}}
        elif command == "без ограничения бюджета":
            remove = ["budget"]
        elif command == "желательно с балконом":
            changes = {"balcony": {"strength": "soft", "value": True}}
        elif command == "обязательно с балконом":
            changes = {"balcony": {"strength": "hard", "value": True}}
        elif command == "туризм":
            changes = {"rental_mode": {"strength": "hard", "value": "holiday"}}
        elif command in {"до 60 евро за ночь", "до 40 евро за ночь"}:
            changes = {"budget": {"strength": "hard", "value": {
                "amount": "60" if "60" in command else "40", "currency": "EUR", "period": "nightly"}}}
        else:
            raise ValueError("unsupported synthetic phrase")
        from app.schemas.ai_search_intent import IntentPatch
        return IntentPatch.model_validate_json(json.dumps({
            "schema_version": "ai-search.v1", "session_id": str(current.session_id),
            "expected_version": current.version, "set": changes, "remove": remove}))


class DistributedHTTPGate:
    def __init__(self, limiter):
        self.limiter = limiter

    async def check(self, key):
        from app.services.ai_search_attempts import AIAttemptRejected
        # Separate, bounded shared Redis buckets for each policy purpose.
        budget = 12 if key.startswith("ai-guest-issue:") else 20 if key.startswith("ai-session-create:") else 240
        try:
            result = await self.limiter.consume("synthetic-lab:http:" + key, budget, 60)
        except (RedisError, OSError, TimeoutError) as error:
            raise AIAttemptRejected("ABUSE_GATE_UNAVAILABLE") from error
        if not result.allowed:
            raise AIAttemptRejected("ATTEMPT_LIMIT", result.retry_after)


def create_app():
    require_lab()
    from app.api.v1.ai_search import AISearchRuntime
    from app.db.session import SessionLocal
    from app.main import app
    from app.repositories.ai_search_quota import QuotaLedger
    from app.repositories.ai_search_sessions import IntentVocabulary, SearchSessions, SessionPolicy
    from app.repositories.ai_verified_cards import VerifiedCardSearch
    from app.schemas.ai_search_quota import LeasePolicy
    from app.services.ai_guest_tokens import GuestPolicy, GuestTokens
    from app.services.ai_http_policy import AIHTTPPolicy
    from app.services.ai_search_attempts import AIAttemptGate
    from app.services.ai_search_execution import TextSearchExecution
    from app.services.rate_limit import RedisRateLimiter

    limiter = RedisRateLimiter(REDIS)
    ledger = QuotaLedger(SessionLocal, LeasePolicy(
        reservation_seconds=60, running_seconds=60, recovery_grace_seconds=30))
    sessions = SearchSessions(ledger, SessionPolicy(inactivity_seconds=3600),
                              IntentVocabulary(frozenset(), frozenset(), frozenset()))
    cards = VerifiedCardSearch(pipeline(SessionLocal), sessions,
                               signing_key=b"synthetic-lab-cursor-independent-key-v1")
    from redis.asyncio import from_url

    from lab.acceptance import ObservedParser
    parser_redis = from_url(REDIS, decode_responses=True)
    execution = TextSearchExecution(sessions, ObservedParser(SyntheticParser(), parser_redis),
                                   AIAttemptGate(limiter, attempts=12, window_seconds=60), cards)
    active = AISearchRuntime(sessions, cards, execution,
        GuestTokens(key=b"synthetic-lab-guest-independent-key-v1", policy=GuestPolicy(ttl_seconds=3600)),
        DistributedHTTPGate(limiter), frozenset({ORIGIN}), 32768,
        AIHTTPPolicy(20, 5, (), ORIGIN))
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        await verify_database(SessionLocal)
        await limiter.ping()
        async with original_lifespan(application):
            application.state.ai_search_runtime = active
            try:
                yield
            finally:
                del application.state.ai_search_runtime
                await limiter.close()
                await parser_redis.aclose()

    app.router.lifespan_context = lifespan
    return app
