"""Explicit offline query orchestration. No public endpoint or provider activation.

Injected parser/attempt gate/query have no defaults. Raw text is neither stored
nor logged here; production outbound privacy approval remains a separate gate.
Clarification and background-alert business policies are deliberately absent.
"""
import asyncio
import hashlib
from contextlib import suppress
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from ..repositories.ai_search_sessions import SearchSessions, SessionError, intent_hash
from ..repositories.ai_verified_cards import VerifiedCardResult
from ..schemas.ai_listing_facts import digest
from ..schemas.ai_search_intent import IntentPatch, SearchIntent, apply_patch
from ..schemas.ai_search_quota import FailureCode, OperationState, QuotaOperation, QuotaSubject, ResultReceipt
from ..schemas.listings import ListingCardSearchRequest
from .ai_search_attempts import AIAttemptRejected


class IntentPatchParser(Protocol):
    async def parse(self, text: str, current: SearchIntent) -> IntentPatch: ...


class AttemptGate(Protocol):
    async def check(self, subject: QuotaSubject) -> None: ...


class CandidateCardQuery(Protocol):
    async def query_candidate(self, subject: QuotaSubject, current: SearchIntent, candidate: SearchIntent,
                              payload: ListingCardSearchRequest) -> VerifiedCardResult: ...
    async def query_result(self, subject: QuotaSubject, result_ref: UUID,
                           payload: ListingCardSearchRequest) -> VerifiedCardResult: ...


@dataclass(frozen=True)
class SearchExecution:
    operation: OperationState
    cards: VerifiedCardResult | None = None
    replay: bool = False


class TextSearchExecution:
    def __init__(self, sessions: SearchSessions, parser: IntentPatchParser, attempts: AttemptGate,
                 query: CandidateCardQuery):
        self.sessions, self.parser, self.attempts, self.query = sessions, parser, attempts, query
        self.ledger = sessions.ledger

    async def execute(self, subject: QuotaSubject, operation: QuotaOperation, text: str,
                      payload: ListingCardSearchRequest) -> SearchExecution:
        """New text message only; voice combines ASR+intent under a future one-debit path.

        A terminal retry never invokes parser/attempt gate/CAS/debit again. Its
        durable receipt retains original count; cards revalidate current public
        visibility against the original committed intent. A DB failure after
        finalize is ambiguous: propagate, then replay from ledger on retry.
        """
        subject = QuotaSubject.model_validate(subject.model_dump())
        operation = QuotaOperation.model_validate(operation.model_dump())
        if operation.channel != "text" or type(text) is not str or not text.strip() or len(text.encode()) > 65_536:
            raise ValueError("bounded nonempty text operation required")
        if hashlib.sha256(text.encode()).hexdigest() != operation.payload_sha256:
            raise ValueError("server payload hash does not match final text")
        payload = ListingCardSearchRequest.model_validate(payload.model_dump())
        if payload.cursor is not None:
            raise ValueError("a new message must not carry a paging cursor")
        filters_hash = digest(payload.model_dump(mode="json"))
        if operation.filters_sha256 is not None and operation.filters_sha256 != filters_hash:
            raise ValueError("server filters hash does not match card request")
        operation = operation.model_copy(update={"filters_sha256": filters_hash})
        reservation = await self.ledger.reserve(subject, operation)
        if reservation.action != "created":
            state = reservation.operation
            cards = None
            if state.status == "succeeded" and state.receipt is not None:
                cards = await self.query.query_result(subject, state.receipt.result_ref, payload)
            return SearchExecution(state, cards, replay=reservation.action == "replay")
        state = await self.ledger.claim(subject, operation)
        phase = FailureCode.BACKEND_FAILURE
        try:
            current = (await self.sessions.get(subject, operation.session_id)).intent
            if current.version != operation.expected_session_version:
                raise SessionError("SESSION_VERSION_CONFLICT")
            await self.attempts.check(subject)
            phase = FailureCode.LLM_FAILURE
            patch = await self.parser.parse(text, current)
            patch = IntentPatch.model_validate_json(patch.model_dump_json(exclude_none=True))
            candidate = apply_patch(current, patch)
            self.sessions.vocabulary.validate(candidate.criteria)
            phase = FailureCode.BACKEND_FAILURE
            cards = await self.query.query_candidate(subject, current, candidate, payload)
            if cards.intent_hash != intent_hash(candidate):
                raise ValueError("query returned a different normalized intent")
            receipt = ResultReceipt(result_ref=uuid4(), count=cards.cards.total)
        except asyncio.CancelledError:
            # No durable success has begun. Cancellation cannot debit. If DB
            # cleanup fails, lease recovery releases it later; never infer again.
            with suppress(Exception):
                await self.ledger.release(subject, operation, state.fence, FailureCode.BACKEND_FAILURE)
            raise
        except Exception as error:  # noqa: BLE001 - map arbitrary injected service failure to a fixed private code
            if isinstance(error, (SessionError, AIAttemptRejected)) and error.code in {code.value for code in FailureCode}:
                phase = FailureCode(error.code)
            released = await self.ledger.release(subject, operation, state.fence, phase)
            return SearchExecution(released)
        # Outside the generic failure/release handler: an acknowledgement error
        # might follow committed CAS+receipt+debit. Retry reads authoritative PG.
        completed = await self.sessions.finalize_patch(subject, operation, state.fence, patch, receipt)
        if completed.status != "succeeded" or completed.receipt is None:
            return SearchExecution(completed)
        # The terminal receipt can be an earlier winner after a concurrent replay.
        if completed.receipt.result_ref != receipt.result_ref:
            cards = await self.query.query_result(subject, completed.receipt.result_ref, payload)
        return SearchExecution(completed, cards)
