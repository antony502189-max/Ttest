"""Explicit offline query orchestration. No public endpoint or provider activation.

Injected parser/attempt gate/query have no defaults. Raw text is neither stored
nor logged here; production outbound privacy approval remains a separate gate.
Clarification is a typed terminal zero-debit outcome. Background alerts remain disabled.
"""
import asyncio
import hashlib
import logging
import math
from contextlib import nullcontext, suppress
from dataclasses import dataclass
from functools import partial
from typing import Protocol
from uuid import UUID, uuid4

from ..repositories.ai_search_sessions import SearchSessions, SessionError, intent_hash
from ..repositories.ai_verified_cards import SourceCoverageUnavailable, VerifiedCardResult
from ..schemas.ai_clarification import REASONS, IntentClarification
from ..schemas.ai_listing_facts import digest
from ..schemas.ai_search_intent import IntentPatch, SearchIntent, apply_patch
from ..schemas.ai_search_quota import FailureCode, OperationState, QuotaOperation, QuotaSubject, ResultReceipt
from ..schemas.listings import ListingCardSearchRequest
from .ai_deepseek_intent import ProviderFailure
from .ai_http_policy import HTTP_DEADLINE
from .ai_observability import EXECUTION_SECONDS, OPERATIONS, PARSER_SECONDS, observe_result
from .ai_search_attempts import AIAttemptRejected


class IntentPatchParser(Protocol):
    async def parse(self, text: str, current: SearchIntent) -> IntentPatch | IntentClarification: ...


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
    result_unavailable: bool = False
    clarification: IntentClarification | None = None

    def __post_init__(self):
        if self.operation.status == "failed" and self.operation.failure_code in REASONS:
            object.__setattr__(self, "clarification", IntentClarification(reason=REASONS[self.operation.failure_code]))
    cards_error: str | None = None


async def terminal_search_result(query: CandidateCardQuery, subject: QuotaSubject, state: OperationState,
                                 payload: ListingCardSearchRequest, *, replay: bool) -> SearchExecution:
    # The owned ledger receipt proves completion independently of card TTL.
    # Card access still uses the full original ownership/expiry checks.
    assert state.status == "succeeded" and state.receipt is not None
    try:
        cards = await query.query_result(subject, state.receipt.result_ref, payload)
    except SessionError as error:
        if error.code not in {"RESULT_EXPIRED_REQUERY_REQUIRED", "RESULT_NOT_FOUND", "SESSION_EXPIRED", "SESSION_NOT_FOUND"}:
            raise
        if error.code == "RESULT_NOT_FOUND":
            logging.getLogger(__name__).warning("ai_result_unavailable", extra={"code": error.code})
        return SearchExecution(state, replay=replay, cards_error=error.code, result_unavailable=True)
    return SearchExecution(state, cards, replay=replay)


class TextSearchExecution:
    def __init__(self, sessions: SearchSessions, parser: IntentPatchParser, attempts: AttemptGate,
                 query: CandidateCardQuery, *, total_budget_seconds: float | None = None):
        self.sessions, self.parser, self.attempts, self.query = sessions, parser, attempts, query
        self.ledger = sessions.ledger
        if total_budget_seconds is None:
            total_budget_seconds = min(15, self.ledger.policy.running_seconds * .9)
        if (type(total_budget_seconds) not in {int, float} or not math.isfinite(total_budget_seconds)
                or not 0 < total_budget_seconds < self.ledger.policy.running_seconds):
            raise ValueError("text deadline must fit inside the running lease")
        self.total_budget_seconds = total_budget_seconds
        # Optional declared parser budget must leave time for query/finalize.
        # This is a configuration guard, not a latency guarantee for the rest
        # of the pipeline; database lease fencing remains authoritative.
        budget = getattr(parser, "total_budget_seconds", None)
        if budget is not None and (type(budget) not in {float, int} or not math.isfinite(budget)
                                   or not 0 < budget < min(self.ledger.policy.running_seconds, total_budget_seconds)):
            raise ValueError("parser deadline must be shorter than running lease")

    async def execute(self, subject: QuotaSubject, operation: QuotaOperation, text: str,
                      payload: ListingCardSearchRequest) -> SearchExecution:
        deadline = asyncio.get_running_loop().time() + self.total_budget_seconds
        http_deadline = HTTP_DEADLINE.get()
        if http_deadline is not None:
            deadline = min(deadline, http_deadline)
        with EXECUTION_SECONDS.time():
            try:
                async with asyncio.timeout_at(deadline):
                    result = await self._execute(subject, operation, text, payload, deadline)
                observe_result(result)
                return result
            except asyncio.CancelledError:
                OPERATIONS.labels("uncertain", "no", "cancelled").inc()
                raise
            except TimeoutError:
                OPERATIONS.labels("uncertain", "no", "timeout").inc()
                raise
            except Exception:
                # A lost commit ACK is uncertain, never a claimed failed debit.
                OPERATIONS.labels("uncertain", "no", "unavailable").inc()
                raise

    async def _execute(self, subject: QuotaSubject, operation: QuotaOperation, text: str,
                       payload: ListingCardSearchRequest, deadline: float) -> SearchExecution:
        """New text message only; voice combines ASR+intent under a future one-debit path.

        A terminal retry never invokes parser/attempt gate/CAS/debit again. Its
        durable receipt retains original count; cards revalidate current public
        visibility against the original committed intent. A DB failure after
        finalize is ambiguous: propagate, then replay from ledger on retry.
        """
        subject = QuotaSubject.model_validate(subject.model_dump())
        operation = QuotaOperation.model_validate(operation.model_dump())
        if (operation.channel != "text" or type(text) is not str or not text.strip()
                or len(text) > 16_384 or len(text.encode()) > 65_536):
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
                return await self._claimed(subject, operation, text, payload, deadline, state)
        except AIAttemptRejected as error:
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError from None
            return SearchExecution(await self.ledger.release(subject, operation, state.fence, FailureCode(error.code)))

    async def _claimed(self, subject: QuotaSubject, operation: QuotaOperation, text: str,
                       payload: ListingCardSearchRequest, deadline: float, state: OperationState) -> SearchExecution:
        phase = FailureCode.BACKEND_FAILURE
        try:
            current = (await self.sessions.get(subject, operation.session_id)).intent
            if current.version != operation.expected_session_version:
                raise SessionError("SESSION_VERSION_CONFLICT")
            await self.attempts.check(subject)
            phase = FailureCode.LLM_FAILURE
            with PARSER_SECONDS.time():
                patch = await self.parser.parse(text, current)
            if isinstance(patch, IntentClarification):
                # Terminal zero-debit receipt. No candidate query, intent CAS
                # or partial update; same-key retries derive the same question.
                return SearchExecution(await self.ledger.release(subject, operation, state.fence, patch.failure_code))
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
                if asyncio.get_running_loop().time() < deadline:
                    async with asyncio.timeout_at(deadline):
                        await self.ledger.release(subject, operation, state.fence, FailureCode.BACKEND_FAILURE)
                # An exhausted HTTP deadline must not start unbounded cleanup.
                # Fenced PG lease recovery releases the reservation later.
            raise
        except Exception as error:  # noqa: BLE001 - map arbitrary injected service failure to a fixed private code
            if isinstance(error, ProviderFailure) and str(error) in {
                "INTENT_CLARIFICATION_REQUIRED", "INTENT_NO_CHANGE", "INTENT_UNSUPPORTED"}:
                phase = FailureCode(str(error))
            if isinstance(error, SourceCoverageUnavailable):
                phase = FailureCode.SOURCE_COVERAGE_UNAVAILABLE
            if isinstance(error, (SessionError, AIAttemptRejected)) and error.code in {code.value for code in FailureCode}:
                phase = FailureCode(error.code)
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError from None
            released = await self.ledger.release(subject, operation, state.fence, phase)
            return SearchExecution(released)
        # Outside the generic failure/release handler: an acknowledgement error
        # might follow committed CAS+receipt+debit. Retry reads authoritative PG.
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError
        completed = await self.sessions.finalize_patch(subject, operation, state.fence, patch, receipt)
        if completed.status != "succeeded" or completed.receipt is None:
            return SearchExecution(completed)
        # The terminal receipt can be an earlier winner after a concurrent replay.
        if completed.receipt.result_ref != receipt.result_ref:
            return await terminal_search_result(self.query, subject, completed, payload, replay=True)
        return SearchExecution(completed, cards)
