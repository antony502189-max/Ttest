"""Explicit saved-search runtime; no provider, guest login or foreground AI API."""
import base64
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text

from ..repositories.ai_saved_searches import RegisteredAISearches
from ..repositories.ai_search_quota import QuotaLedger
from ..repositories.ai_search_sessions import IntentVocabulary, SearchSessions, SessionPolicy
from ..schemas.ai_search_quota import LeasePolicy
from .ai_erasure_journal import configured_journal, replay_erasure
from .ai_housing_catalog import housing_pipeline
from .ai_saved_handoff import SavedHandoffSigner
from .ai_saved_notifications import SavedNotificationWorker


@dataclass(frozen=True)
class SavedRuntime:
    repo: RegisteredAISearches
    signer: SavedHandoffSigner
    worker: SavedNotificationWorker


def configured_saved_runtime(factory) -> SavedRuntime | None:
    mode = os.environ.get("AI_SAVED_SEARCH_MODE")
    if not mode:
        return None
    if mode != "signed-housing-inapp.v1":
        raise ValueError("AI_SAVED_CONFIGURATION_INVALID")
    # Secret file mount; no default key or reuse of cursor/guest/erasure keys.
    path = Path(os.environ.get("AI_SAVED_HANDOFF_KEY_FILE", ""))
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("AI_HANDOFF_KEY_REQUIRED")
    key = base64.b64decode(path.read_bytes().strip(), validate=True)
    signer = SavedHandoffSigner(key)
    pipeline = housing_pipeline(factory, resolver_version="housing-main.v1")
    vocabulary = pipeline.vocabulary
    sessions = SearchSessions(QuotaLedger(factory, LeasePolicy(reservation_seconds=60,
        running_seconds=60, recovery_grace_seconds=30)), SessionPolicy(inactivity_seconds=86400),
        IntentVocabulary(vocabulary.amenity_codes, vocabulary.catalog_other_codes, vocabulary.municipality_zones),
        require_auth_owner=True)
    repo = RegisteredAISearches(sessions, pipeline)
    # Explicit bounded background policy; zero provider IO / SMTP.
    return SavedRuntime(repo, signer, SavedNotificationWorker(repo, daily_limit=20, batch_size=20, cadence_seconds=300))


async def preflight_saved_runtime(runtime: SavedRuntime) -> None:
    async with runtime.repo.connections() as conn:
        revision = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalars().all()
        if revision != ["0080_ai_saved_rematch"]:
            raise ValueError("AI_SAVED_DATABASE_REVISION_MISMATCH")
    journal = configured_journal()
    if journal is None:
        raise ValueError("AI_ERASURE_JOURNAL_REQUIRED")
    await replay_erasure(runtime.repo.connections, journal)


def install_saved_runtime(app, factory) -> None:
    configured = configured_saved_runtime(factory)
    # Turning off new saves must not turn off deletion/restore protection for
    # private snapshots already retained by this database.
    journal_configured = any(os.environ.get(key) for key in ("AI_ERASURE_JOURNAL_PATH", "AI_ERASURE_JOURNAL_KEY", "AI_ERASURE_JOURNAL_KEY_FILE"))
    if configured is None and not journal_configured:
        return
    original = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with original(application):
            if configured is not None:
                await preflight_saved_runtime(configured)
                application.state.ai_saved_runtime = configured
            else:
                journal = configured_journal()
                if journal is None:
                    raise ValueError("AI_ERASURE_JOURNAL_REQUIRED")
                await replay_erasure(factory, journal)
            try:
                yield
            finally:
                if configured is not None:
                    del application.state.ai_saved_runtime
    app.router.lifespan_context = lifespan
