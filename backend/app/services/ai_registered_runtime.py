"""Opt-in native account search. No guest issuance, external parser or ingestion."""
import base64
import hashlib
import json
import os
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from ..core.config import get_settings
from ..models import ExternalListingSource
from ..repositories.ai_search_sessions import IntentVocabulary, SessionPolicy
from ..schemas.ai_search_quota import LeasePolicy
from .ai_guest_tokens import GuestPolicy, GuestTokens
from .ai_housing_catalog import housing_pipeline
from .ai_housing_input import housing_patch
from .ai_http_policy import AIHTTPPolicy
from .ai_local_asr import LocalPCMTranscriber
from .ai_saved_handoff import SavedHandoffSigner
from .ai_text_runtime import assemble_text_runtime, install_text_runtime
from .ai_voice_execution import VoicePolicy, VoiceSearchExecution
from .rate_limit import RedisRateLimiter

MODEL_FILES = {
    "config.json": "b55496ac7940a7ae47d2c01eab40edfd8701feec1229d9cce3b40014383fb828",
    "tokenizer.json": "fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab",
    "vocabulary.txt": "34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913",
    "model.bin": "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671",
}


def _file(variable: str, maximum: int = 20000) -> Path:
    path = Path(os.environ.get(variable, ""))
    if not path.is_absolute() or path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError("AI_REGISTERED_CONFIGURATION_REQUIRED")
    return path


class RegisteredHousingParser:
    def __init__(self, vocabulary):
        self.vocabulary = vocabulary

    async def parse(self, text, current):
        # Coverage/currentness is checked independently by candidate SQL before
        # publication/debit, including meaningful zero and unknown fact outcomes.
        return housing_patch(text, current, self.vocabulary)


def verify_registered_resources(root: Path = Path("/sys/fs/cgroup")) -> None:
    """The full native composition must retain the reviewed voice resource cap."""
    try:
        quota, period = (root / "cpu.max").read_text().split()
        bounded = (int((root / "memory.max").read_text()) == 1536 * 1024 * 1024
            and int((root / "memory.swap.max").read_text()) == 0
            and int(quota) > 0 and int(period) > 0 and int(quota) / int(period) <= 2)
    except (OSError, ValueError):
        bounded = False
    if not bounded:
        raise ValueError("AI_REGISTERED_RESOURCE_LIMITS_REQUIRED")


def verify_registered_model(model: Path) -> None:
    if not model.is_absolute() or model.is_symlink() or not model.is_dir():
        raise ValueError("AI_REGISTERED_ASR_ASSETS_REQUIRED")
    if {path.name for path in model.iterdir()} != set(MODEL_FILES):
        raise ValueError("AI_REGISTERED_ASR_MODEL_MISMATCH")
    for name, expected in MODEL_FILES.items():
        path = model / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("AI_REGISTERED_ASR_MODEL_MISMATCH")
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                raise ValueError("AI_REGISTERED_ASR_MODEL_MISMATCH")


def configured_registered_runtime(factory):
    mode = os.environ.get("AI_REGISTERED_SEARCH_MODE")
    if not mode:
        return None
    if mode != "local-housing-accounts.v1" or os.environ.get("AI_SAVED_SEARCH_MODE") != "signed-housing-inapp.v1":
        raise ValueError("AI_REGISTERED_CONFIGURATION_INVALID")
    keys = json.loads(_file("AI_REGISTERED_KEYS_FILE", 4096).read_bytes())
    if set(keys) != {"schema", "ip", "cursor"} or keys["schema"] != "ai-registered-keys.v1":
        raise ValueError("AI_REGISTERED_KEYS_REQUIRED")
    ip_key, cursor_key = (base64.b64decode(keys[name], validate=True) for name in ("ip", "cursor"))
    if len(ip_key) != 32 or len(cursor_key) != 32:
        raise ValueError("AI_REGISTERED_KEYS_REQUIRED")
    cohort = json.loads(_file("AI_SAVED_COHORT_FILE").read_bytes())
    if set(cohort) != {"schema", "source_ids"} or cohort["schema"] != "ai-saved-cohort.v1":
        raise ValueError("AI_REGISTERED_COHORT_REQUIRED")
    source_ids = tuple(UUID(value) for value in cohort["source_ids"])
    signer = SavedHandoffSigner(base64.b64decode(_file("AI_SAVED_HANDOFF_KEY_FILE", 4096).read_bytes().strip(), validate=True))
    settings = get_settings()
    if not settings.redis_url:
        raise ValueError("AI_REGISTERED_REDIS_REQUIRED")
    origin = settings.frontend_app_url.rstrip("/")
    pipeline = housing_pipeline(factory, resolver_version="housing-main.v1")
    vocab = pipeline.vocabulary
    parser = RegisteredHousingParser(IntentVocabulary(vocab.amenity_codes, vocab.catalog_other_codes, vocab.municipality_zones))
    # The GuestTokens instance supplies keyed IP/subject hashes only. The native
    # auth_only route rejects anonymous/cookie-only callers before issue/read.
    runtime = assemble_text_runtime(pipeline=pipeline, parser=parser, limiter=RedisRateLimiter(settings.redis_url),
        lease_policy=LeasePolicy(reservation_seconds=60, running_seconds=60, recovery_grace_seconds=30),
        session_policy=SessionPolicy(inactivity_seconds=86400),
        guests=GuestTokens(key=ip_key, policy=GuestPolicy(ttl_seconds=86400)), cursor_key=cursor_key,
        http_policy=AIHTTPPolicy(24.5, 3, (), origin), origins=frozenset({origin}), max_body_bytes=32768,
        execution_seconds=15, source_ids=source_ids)
    # Voice assets must be explicitly provisioned and reviewed separately. Never
    # download on startup or enable an audio endpoint with missing local assets.
    python = _file("AI_REGISTERED_ASR_PYTHON", 100_000_000)
    model = Path(os.environ.get("AI_REGISTERED_ASR_MODEL", ""))
    verify_registered_model(model)
    asr = LocalPCMTranscriber(python=python, model=model, seconds=18, prewarm=True)
    runtime = replace(runtime, auth_only=True, saved_handoff=signer,
        voice=VoiceSearchExecution(runtime.sessions, asr, parser, runtime.execution.attempts, runtime.cards,
            VoicePolicy(media_types=("audio/wav",), max_audio_bytes=480044, max_transcript_bytes=8000,
                asr_budget_seconds=18, intent_budget_seconds=2, total_budget_seconds=24)))
    return runtime, asr


def install_registered_runtime(app, factory) -> None:
    configured = configured_registered_runtime(factory)
    if configured is None:
        return
    runtime, asr = configured
    install_text_runtime(app, runtime)
    original = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        try:
            async with original(application):
                verify_registered_resources()
                async with factory() as conn:
                    anchors = (await conn.execute(select(ExternalListingSource.id).where(
                        ExternalListingSource.id.in_(runtime.cards.source_ids)))).scalars().all()
                    if set(anchors) != set(runtime.cards.source_ids):
                        raise ValueError("AI_REGISTERED_COHORT_UNAVAILABLE")
                await asr.start()
                yield
        finally:
            await asr.close()
    app.router.lifespan_context = lifespan
