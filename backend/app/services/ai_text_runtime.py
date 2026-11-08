"""Explicit application composition for text search; importing never enables AI.

The deployment supplies its separately reviewed parser and data policy. No lab
fixtures, provider credentials, outbound approval or migrations are inferred here.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from ..api.v1.ai_search import AISearchRuntime
from ..repositories.ai_fact_pipeline import FactPipeline
from ..repositories.ai_search_quota import QuotaLedger
from ..repositories.ai_search_sessions import IntentVocabulary, SearchSessions, SessionPolicy
from ..repositories.ai_verified_cards import VerifiedCardSearch
from ..schemas.ai_search_quota import LeasePolicy
from .ai_erasure_journal import configured_journal, replay_erasure
from .ai_guest_tokens import GuestTokens
from .ai_http_policy import AIHTTPPolicy
from .ai_operating_limits import OperatingAttemptGate, OperatingHTTPGate
from .ai_search_execution import IntentPatchParser, TextSearchExecution
from .rate_limit import RedisRateLimiter

DATABASE_REVISION = "0079_ai_operating_policy"


def assemble_text_runtime(*, pipeline: FactPipeline, parser: IntentPatchParser,
                          limiter: RedisRateLimiter, lease_policy: LeasePolicy,
                          session_policy: SessionPolicy, guests: GuestTokens,
                          cursor_key: bytes, http_policy: AIHTTPPolicy,
                          origins: frozenset[str], max_body_bytes: int,
                          execution_seconds: float) -> AISearchRuntime:
    """Connect the existing UI API, durable quota, parser and verified SQL reads.

    Construction does no database/Redis/provider IO and does not modify app.main.
    The supplied pipeline selects the reviewed resolver/vocabulary/freshness;
    there is no ingestion, proof preparation or source refresh during a query.
    """
    if pipeline.operating_policy is None:
        raise ValueError("explicit source freshness policy required")
    if cursor_key in guests.verification_keys:
        raise ValueError("independent cursor and guest signing keys required")
    if execution_seconds >= http_policy.request_seconds:
        raise ValueError("execution deadline must be shorter than HTTP deadline")
    vocabulary = pipeline.vocabulary
    sessions = SearchSessions(QuotaLedger(pipeline.sessions, lease_policy), session_policy,
        IntentVocabulary(vocabulary.amenity_codes, vocabulary.catalog_other_codes,
                         vocabulary.municipality_zones), require_auth_owner=True)
    cards = VerifiedCardSearch(pipeline, sessions, signing_key=cursor_key)
    execution = TextSearchExecution(sessions, parser, OperatingAttemptGate(limiter), cards,
                                    total_budget_seconds=execution_seconds)
    return AISearchRuntime(sessions, cards, execution, guests, OperatingHTTPGate(limiter),
                           origins, max_body_bytes, http_policy)


def install_text_runtime(app: FastAPI, runtime: AISearchRuntime) -> None:
    """Install an explicit lifespan, publishing capabilities only after preflight.

    Requires an already initialized and bound independent deletion journal.
    replay_erasure verifies that binding and completes outstanding erasures before
    serving traffic. It cannot create a replacement journal or migrate a database.
    The operator must separately supervise maintain_ai_search (recovery/retention).
    The lifespan owns the runtime's Redis limiter; the deployment owns its parser.
    """
    if not isinstance(runtime, AISearchRuntime) or not isinstance(runtime.http_gate, OperatingHTTPGate):
        raise TypeError("explicit runtime and distributed HTTP gate required")
    if getattr(app.state, "ai_text_runtime_installed", False) or getattr(app.state, "ai_search_runtime", None):
        raise ValueError("AI runtime already installed")
    app.state.ai_text_runtime_installed = True
    original_lifespan = app.router.lifespan_context
    limiter = runtime.http_gate.limiter

    @asynccontextmanager
    async def lifespan(application):
        try:
            async with original_lifespan(application):
                if getattr(application.state, "ai_search_runtime", None) is not None:
                    raise ValueError("AI runtime already active")
                async with runtime.sessions.ledger.sessions() as connection:
                    revisions = (await connection.execute(text("SELECT version_num FROM alembic_version"))).scalars().all()
                    if revisions != [DATABASE_REVISION]:
                        raise ValueError("AI_DATABASE_REVISION_MISMATCH")
                if not await limiter.ping():
                    raise ValueError("AI_REDIS_UNAVAILABLE")
                journal = configured_journal()
                if journal is None:
                    raise ValueError("AI_ERASURE_JOURNAL_REQUIRED")
                await replay_erasure(runtime.sessions.ledger.sessions, journal)
                application.state.ai_search_runtime = runtime
                try:
                    yield
                finally:
                    # Preserve an explicit operator replacement/kill switch.
                    if getattr(application.state, "ai_search_runtime", None) is runtime:
                        del application.state.ai_search_runtime
        finally:
            await limiter.close()

    app.router.lifespan_context = lifespan
