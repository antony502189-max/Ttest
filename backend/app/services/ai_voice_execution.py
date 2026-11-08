"""Injected ASR+intent under one durable quota operation; opt-in HTTP composition."""
import asyncio
import hashlib
from collections.abc import Awaitable, Callable
from contextlib import nullcontext, suppress
from functools import partial
from typing import Literal, Protocol
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from ..repositories.ai_search_sessions import SearchSessions, SessionError, intent_hash
from ..repositories.ai_verified_cards import SourceCoverageUnavailable
from ..schemas.ai_clarification import IntentClarification
from ..schemas.ai_listing_facts import digest
from ..schemas.ai_search_intent import IntentPatch, apply_patch
from ..schemas.ai_search_quota import (
    FailureCode,
    OperationState,
    QuotaOperation,
    QuotaSubject,
    ResultReceipt,
    StrictContract,
)
from ..schemas.listings import ListingCardSearchRequest
from .ai_deepseek_intent import ProviderFailure
from .ai_http_policy import HTTP_DEADLINE
from .ai_search_attempts import AIAttemptRejected
from .ai_search_execution import (
    AttemptGate,
    CandidateCardQuery,
    IntentPatchParser,
    SearchExecution,
    terminal_search_result,
)

AudioMedia = Literal["audio/wav", "audio/webm", "audio/ogg", "audio/mp4"]


class VoicePolicy(StrictContract):
    # Explicit synthetic/engineering policy only. No production media, duration,
    # retention or consent defaults are inferred from these technical bounds.
    media_types: tuple[AudioMedia, ...] = Field(min_length=1, max_length=4)
    max_audio_bytes: int = Field(ge=1, le=20_971_520)
    max_transcript_bytes: int = Field(ge=1, le=65_536)
    asr_budget_seconds: float = Field(gt=0, le=30)
    intent_budget_seconds: float = Field(gt=0, le=30)
    total_budget_seconds: float = Field(gt=0, le=120)

    @model_validator(mode="after")
    def allocation(self):
        if len(set(self.media_types)) != len(self.media_types):
            raise ValueError("duplicate media policy")
        if self.asr_budget_seconds + self.intent_budget_seconds >= self.total_budget_seconds:
            raise ValueError("combined provider budgets must leave query time")
        return self


class AudioTranscriber(Protocol):
    async def transcribe(self, audio: bytes, media_type: AudioMedia) -> str: ...


async def _bounded[T](work: Callable[[], Awaitable[T]], seconds: float) -> T:
    deadline = asyncio.get_running_loop().time() + seconds
    async with asyncio.timeout_at(deadline):
        result = await work()
        # Also catch bounded synchronous work or an injected provider swallowing
        # cancellation before its timer callback gets a turn.
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError
        return result


class VoiceSearchExecution:
    def __init__(self, sessions: SearchSessions, asr: AudioTranscriber, parser: IntentPatchParser,
                 attempts: AttemptGate, query: CandidateCardQuery, policy: VoicePolicy):
        self.sessions, self.asr, self.parser, self.attempts, self.query = sessions, asr, parser, attempts, query
        self.ledger = sessions.ledger
        self.policy = VoicePolicy.model_validate(policy.model_dump())
        if self.policy.total_budget_seconds >= self.ledger.policy.running_seconds:
            raise ValueError("voice deadline must leave time within the running lease for finalize")

    async def execute(self, subject: QuotaSubject, key: UUID, session_id: UUID, version: int,
                      audio: bytes, media_type: AudioMedia, payload: ListingCardSearchRequest) -> SearchExecution:
        # Include pool/reserve/claim, replay reads, cleanup and atomic finalize
        # in the caller's budget, even without an HTTP wrapper.
        deadline = asyncio.get_running_loop().time() + self.policy.total_budget_seconds
        http_deadline = HTTP_DEADLINE.get()
        if http_deadline is not None:
            deadline = min(deadline, http_deadline)
        async with asyncio.timeout_at(deadline):
            return await self._execute(subject, key, session_id, version, audio, media_type, payload, deadline)

    async def _execute(self, subject: QuotaSubject, key: UUID, session_id: UUID, version: int,
                       audio: bytes, media_type: AudioMedia, payload: ListingCardSearchRequest,
                       deadline: float) -> SearchExecution:
        subject = QuotaSubject.model_validate(subject.model_dump())
        if type(audio) is not bytes or not 0 < len(audio) <= self.policy.max_audio_bytes:
            raise ValueError("VOICE_AUDIO_INVALID")
        if media_type not in self.policy.media_types:
            raise ValueError("VOICE_MEDIA_INVALID")
        payload = ListingCardSearchRequest.model_validate(payload.model_dump())
        if payload.cursor is not None:
            raise ValueError("a new voice message must not carry a paging cursor")
        # Hash the final immutable bytes on the server. Media and the complete
        # validated card request are part of the same fingerprint. Text v1
        # fingerprints and the original operation key are never changed.
        operation = QuotaOperation(idempotency_key=key, channel="voice", session_id=session_id,
            expected_session_version=version, payload_sha256=hashlib.sha256(audio).hexdigest(),
            filters_sha256=digest({"media_type": media_type, "search": payload.model_dump(mode="json")}))
        reservation = await self.ledger.reserve(subject, operation,
            admit=partial(self.sessions.admit_operation, subject=subject, operation=operation),
            serialize=partial(self.sessions.lock_subject, subject=subject))
        if reservation.action != "created":
            state = reservation.operation
            cards = None
            if state.status == "succeeded" and state.receipt is not None:
                return await terminal_search_result(self.query, subject, state, payload, replay=reservation.action == "replay")
            return SearchExecution(state, cards, replay=reservation.action == "replay")
        state = await self.ledger.claim(subject, operation)
        slots = getattr(self.attempts, "inference", None)
        try:
            async with slots(subject, deadline=deadline) if slots else nullcontext():
                return await self._claimed(subject, operation, session_id, version, audio, media_type, payload, deadline, state)
        except AIAttemptRejected as error:
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError from None
            return SearchExecution(await self.ledger.release(subject, operation, state.fence, FailureCode(error.code)))

    async def _claimed(self, subject: QuotaSubject, operation: QuotaOperation, session_id: UUID, version: int,
                       audio: bytes, media_type: AudioMedia, payload: ListingCardSearchRequest,
                       deadline: float, state: OperationState) -> SearchExecution:
        phase = FailureCode.BACKEND_FAILURE
        try:
            async with asyncio.timeout_at(deadline):
                current = (await self.sessions.get(subject, session_id)).intent
                if current.version != version:
                    raise SessionError("SESSION_VERSION_CONFLICT")
                await self.attempts.check(subject)
                if asyncio.get_running_loop().time() >= deadline:
                    raise TimeoutError
                phase = FailureCode.ASR_FAILURE
                transcript = await _bounded(lambda: self.asr.transcribe(audio, media_type), self.policy.asr_budget_seconds)
                if (type(transcript) is not str or not transcript.strip() or len(transcript) > 16_384
                        or len(transcript.encode()) > self.policy.max_transcript_bytes):
                    raise ValueError("VOICE_TRANSCRIPT_INVALID")
                phase = FailureCode.LLM_FAILURE
                patch = await _bounded(lambda: self.parser.parse(transcript, current), self.policy.intent_budget_seconds)
                if isinstance(patch, IntentClarification):
                    return SearchExecution(await self.ledger.release(subject, operation, state.fence, patch.failure_code))
                patch = IntentPatch.model_validate_json(patch.model_dump_json(exclude_none=True))
                candidate = apply_patch(current, patch)
                self.sessions.vocabulary.validate(candidate.criteria)
                phase = FailureCode.BACKEND_FAILURE
                cards = await self.query.query_candidate(subject, current, candidate, payload)
                if cards.intent_hash != intent_hash(candidate) or asyncio.get_running_loop().time() >= deadline:
                    raise ValueError("VOICE_QUERY_INVALID_OR_LATE")
                receipt = ResultReceipt(result_ref=uuid4(), count=cards.cards.total)
        except asyncio.CancelledError:
            with suppress(Exception):
                # Cancellation cleanup gets only the remaining own/HTTP budget.
                # On expiry leave the durable fence/reservation for recovery.
                if asyncio.get_running_loop().time() < deadline:
                    async with asyncio.timeout_at(deadline):
                        await self.ledger.release(subject, operation, state.fence, FailureCode.BACKEND_FAILURE)
            raise
        except Exception as error:  # noqa: BLE001 - no raw audio/transcript/provider/SQL export
            if isinstance(error, ProviderFailure) and str(error) in {
                "INTENT_CLARIFICATION_REQUIRED", "INTENT_NO_CHANGE", "INTENT_UNSUPPORTED"}:
                phase = FailureCode(str(error))
            if isinstance(error, SourceCoverageUnavailable):
                phase = FailureCode.SOURCE_COVERAGE_UNAVAILABLE
            if isinstance(error, (SessionError, AIAttemptRejected)) and error.code in {code.value for code in FailureCode}:
                phase = FailureCode(error.code)
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError from None
            return SearchExecution(await self.ledger.release(subject, operation, state.fence, phase))
        # Finalize is deliberately outside release/cancellation cleanup: an ack
        # loss may follow committed session+receipt+debit. Retry only replays PG.
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError
        completed = await self.sessions.finalize_patch(subject, operation, state.fence, patch, receipt)
        if completed.status != "succeeded" or completed.receipt is None:
            return SearchExecution(completed)
        if completed.receipt.result_ref != receipt.result_ref:
            return await terminal_search_result(self.query, subject, completed, payload, replay=True)
        return SearchExecution(completed, cards)
