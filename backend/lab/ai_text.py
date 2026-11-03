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


def require_lab(*, closed_ui=False):
    # Exact dedicated destinations; no caller-supplied application DB/provider.
    expected = {"APP_ENV": "test", "AI_SYNTHETIC_LAB": MARKER,
                "DATABASE_URL": DATABASE, "REDIS_URL": REDIS,
                "FRONTEND_APP_URL": ORIGIN, "FRONTEND_ORIGINS": ORIGIN,
                "EXTERNAL_IMPORT_ENABLED": "false", "EXTERNAL_REMOVAL_CHECK_ENABLED": "false"}
    if any(os.environ.get(key) != value for key, value in expected.items()):
        raise RuntimeError("use only the dedicated ai-text-lab launcher/configuration")
    allowed = {"finite", "decision-transport-fixture"}
    if closed_ui:
        if os.environ.get("AI_LAB_PARSER") != "closed-live-synthetic":
            raise RuntimeError("explicit closed LIVE synthetic UI composition required")
        allowed = {"closed-live-synthetic"}
    if os.environ.get("AI_LAB_PARSER", "finite") not in allowed:
        raise RuntimeError("unknown lab parser; live provider activation forbidden")
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
    from app.services.ai_fact_quality import FactQualityPolicy
    vocabulary = FactVocabulary(amenity_codes=frozenset(), catalog_other_codes=frozenset(),
                                tenant_group_codes=frozenset(), municipality_zones=frozenset())
    return FactPipeline(factory, FactQueuePolicy(lease_seconds=60, max_attempts=2, retry_delay_seconds=1),
                        vocabulary, resolver_version="synthetic-lab.v1",
                        operating_policy=FactQualityPolicy(price_max_age_seconds=86400,
                            policy_max_age_seconds=86400, evidence_retention_seconds=604800))


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
    return _assemble_app()


def _assemble_app(parser_factory=None):
    # Shared wiring only. Public composition roots must validate their own
    # environment before entering here; app.main never calls this function.
    from app.api.v1.ai_search import AISearchRuntime
    from app.db.session import SessionLocal
    from app.main import app
    from app.repositories.ai_search_quota import QuotaLedger
    from app.repositories.ai_search_sessions import IntentVocabulary, SearchSessions, SessionPolicy
    from app.repositories.ai_verified_cards import VerifiedCardSearch
    from app.schemas.ai_search_quota import LeasePolicy
    from app.services.ai_guest_tokens import GuestPolicy, GuestTokens
    from app.services.ai_http_policy import AIHTTPPolicy
    from app.services.ai_operating_limits import OperatingAttemptGate, OperatingHTTPGate
    from app.services.ai_search_execution import TextSearchExecution
    from app.services.rate_limit import RedisRateLimiter

    limiter = RedisRateLimiter(REDIS)
    ledger = QuotaLedger(SessionLocal, LeasePolicy(
        reservation_seconds=60, running_seconds=60, recovery_grace_seconds=30))
    sessions = SearchSessions(ledger, SessionPolicy(inactivity_seconds=86400),
                              IntentVocabulary(frozenset(), frozenset(), frozenset()), require_auth_owner=True)
    cards = VerifiedCardSearch(pipeline(SessionLocal), sessions,
                               signing_key=b"synthetic-lab-cursor-independent-key-v1")
    from redis.asyncio import from_url

    from lab.acceptance import ObservedParser
    parser_redis = from_url(REDIS, decode_responses=True)
    original_finalize = sessions.finalize_patch

    async def finalize_with_ack_fault(subject, operation, *args, **kwargs):
        result = await original_finalize(subject, operation, *args, **kwargs)
        key = f"lab-acceptance:{operation.session_id}:{operation.expected_session_version}:commit-ack"
        if await parser_redis.getdel(key):
            raise ConnectionError("synthetic lost commit acknowledgement")
        return result

    sessions.finalize_patch = finalize_with_ack_fault
    if parser_factory is not None:
        parser = parser_factory()
    elif os.environ.get("AI_LAB_PARSER", "finite") == "decision-transport-fixture":
        from lab.decision_parser import LocalDecisionParser
        parser = LocalDecisionParser(parser_redis)
    else:
        parser = ObservedParser(SyntheticParser(), parser_redis)
    execution = TextSearchExecution(sessions, parser,
                                   OperatingAttemptGate(limiter), cards)
    active = AISearchRuntime(sessions, cards, execution,
        GuestTokens(key=b"synthetic-lab-guest-independent-key-v1", policy=GuestPolicy(ttl_seconds=604800)),
        OperatingHTTPGate(limiter), frozenset({ORIGIN}), 32768,
        AIHTTPPolicy(20, 3, (), ORIGIN))
    import httpx

    from lab.runtime_contract import LabRuntime, RuntimePairing
    transport = getattr(parser, "transport", None)
    kind = "mock" if isinstance(transport, httpx.MockTransport) else "none" if transport is None else (
        "mock" if isinstance(getattr(transport, "inner", None), httpx.MockTransport) else "https")
    contract = LabRuntime.create(os.environ.get("AI_LAB_PARSER", "finite"),
                                 os.environ.get("AI_LAB_SOURCE_SHA"), kind)
    if not any(item.cls is RuntimePairing for item in app.user_middleware):
        app.add_middleware(RuntimePairing)
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        await verify_database(SessionLocal)
        await limiter.ping()
        from app.services.ai_erasure_journal import bind_journal, configured_journal, replay_erasure
        journal = configured_journal()
        if journal is None:
            raise RuntimeError("AI_ERASURE_JOURNAL_REQUIRED")
        # Only this explicitly marked synthetic lab may establish the initial
        # DB binding. A replacement journal never matches an existing binding.
        await bind_journal(SessionLocal, journal, initialize=True)
        await replay_erasure(SessionLocal, journal)
        async with original_lifespan(application):
            application.state.ai_lab_runtime = contract
            if os.environ.get("AI_SYNTHETIC_SEARCH_DISABLED", "false") == "false":
                application.state.ai_search_runtime = active
            try:
                yield
            finally:
                del application.state.ai_lab_runtime
                if hasattr(application.state, "ai_search_runtime"):
                    del application.state.ai_search_runtime
                await limiter.close()
                await parser_redis.aclose()

    app.router.lifespan_context = lifespan
    return app
