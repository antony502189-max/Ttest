"""AI-08: normalized PG sessions and the real AI-07 finalize callback."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.ai_search_session import AISearchResult, AISearchSession
from ..schemas.ai_search_intent import Criteria, IntentPatch, SearchIntent, apply_patch
from ..schemas.ai_search_quota import (
    FailureCode,
    OperationState,
    QuotaOperation,
    QuotaSubject,
    ResultReceipt,
    StrictContract,
)
from .ai_search_quota import QuotaLedger, SessionCommit, SessionCommitRejected, SessionVersionConflict, _now


class SessionError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class SessionPolicy(StrictContract):
    # Explicit engineering configuration, not a 24h or retention product default.
    inactivity_seconds: int = Field(ge=1, le=2_592_000)


class SessionSnapshot(StrictContract):
    intent: SearchIntent
    expires_at: datetime


class CommittedIntent(StrictContract):
    result_ref: UUID
    count: int = Field(ge=0)
    intent: SearchIntent
    intent_hash: str


@dataclass(frozen=True)
class IntentVocabulary:
    # Server-owned reviewed catalog vocabulary. No implicit permissive defaults.
    amenity_codes: frozenset[str]
    accommodation_codes: frozenset[str]
    zones: frozenset[tuple[str, str]]

    def validate(self, criteria: Criteria) -> None:
        if criteria.amenities and not set(criteria.amenities.value) <= self.amenity_codes:
            raise ValueError("unsupported amenity code")
        if criteria.accommodation:
            value = criteria.accommodation.value
            if value.kind == "catalog_other" and value.catalog_code not in self.accommodation_codes:
                raise ValueError("unsupported accommodation catalog code")
        if criteria.geography:
            geography = criteria.geography.value
            if geography.zone_id is not None and (geography.municipality_code, geography.zone_id) not in self.zones:
                raise ValueError("unsupported municipality zone")


def intent_hash(intent: SearchIntent) -> str:
    canonical = json.dumps(intent.model_dump(mode="json", exclude_none=True), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


class SearchSessions:
    def __init__(self, ledger: QuotaLedger, policy: SessionPolicy, vocabulary: IntentVocabulary):
        self.ledger, self.policy, self.vocabulary = ledger, policy, vocabulary

    @staticmethod
    def _owned(subject: QuotaSubject, session_id: UUID):
        return (
            AISearchSession.id == session_id,
            AISearchSession.subject_kind == subject.kind,
            AISearchSession.subject_id == subject.id,
        )

    def _decode(self, row: AISearchSession) -> SearchIntent:
        try:
            intent = SearchIntent.model_validate_json(
                json.dumps(
                    {
                        "schema_version": row.schema_version,
                        "taxonomy_version": row.taxonomy_version,
                        "session_id": str(row.id),
                        "version": row.version,
                        "criteria": row.criteria,
                    }
                )
            )
            self.vocabulary.validate(intent.criteria)
            return intent
        except (ValueError, TypeError) as error:
            raise SessionError("SESSION_STATE_INVALID") from error

    async def _read(
        self,
        conn: AsyncSession,
        subject: QuotaSubject,
        session_id: UUID,
        *,
        lock: bool = False,
        allow_expired: bool = False,
    ) -> tuple[AISearchSession, SearchIntent]:
        query = (
            select(AISearchSession).where(*self._owned(subject, session_id)).execution_options(populate_existing=True)
        )
        row = await conn.scalar(query.with_for_update() if lock else query)
        if row is None:
            raise SessionError("SESSION_NOT_FOUND")
        # Clock after lock acquisition, never before a potentially long wait.
        if not allow_expired and (row.closed_at is not None or row.expires_at <= await _now(conn)):
            raise SessionError("SESSION_EXPIRED")
        return row, self._decode(row)

    async def _create(self, conn: AsyncSession, subject: QuotaSubject) -> SessionSnapshot:
        now = await _now(conn)
        intent = SearchIntent(
            schema_version="ai-search.v1",
            taxonomy_version="rental.v1",
            session_id=uuid4(),
            version=0,
            criteria=Criteria(),
        )
        expiry = now + timedelta(seconds=self.policy.inactivity_seconds)
        conn.add(
            AISearchSession(
                id=intent.session_id,
                subject_kind=subject.kind,
                subject_id=subject.id,
                schema_version=intent.schema_version,
                taxonomy_version=intent.taxonomy_version,
                version=0,
                criteria={},
                expires_at=expiry,
                created_at=now,
                updated_at=now,
            )
        )
        await conn.flush()
        return SessionSnapshot(intent=intent, expires_at=expiry)

    async def create(self, subject: QuotaSubject) -> SessionSnapshot:
        async with self.ledger.sessions.begin() as conn:
            return await self._create(conn, subject)

    async def get(self, subject: QuotaSubject, session_id: UUID) -> SessionSnapshot:
        async with self.ledger.sessions() as conn:
            row, intent = await self._read(conn, subject, session_id)
            return SessionSnapshot(intent=intent, expires_at=row.expires_at)

    async def reset(self, subject: QuotaSubject, session_id: UUID, expected_version: int) -> SessionSnapshot:
        """Explicit caller command only. Never inferred from missing patch fields."""
        if type(expected_version) is not int or not 0 <= expected_version <= 2_147_483_647:
            raise ValueError("a bounded expected version is required")
        async with self.ledger.sessions.begin() as conn:
            row, _ = await self._read(conn, subject, session_id, lock=True, allow_expired=True)
            if row.closed_at is not None or row.version != expected_version:
                raise SessionError("SESSION_VERSION_CONFLICT")
            row.updated_at = await _now(conn)
            row.expires_at = row.updated_at
            row.closed_at = row.updated_at
            # New identity; old requests can never resurrect or mutate it.
            return await self._create(conn, subject)

    def commit_patch(
        self, subject: QuotaSubject, operation: QuotaOperation, patch: IntentPatch, receipt: ResultReceipt
    ) -> SessionCommit:
        """Build the local-SQL callback; execute only through ledger finalize."""

        async def commit(conn: AsyncSession, session_id: UUID, version: int) -> None:
            if patch.session_id != session_id or patch.expected_version != version:
                raise SessionCommitRejected(FailureCode.SESSION_STATE_INVALID)
            try:
                row, current = await self._read(conn, subject, session_id, lock=True)
            except SessionError as error:
                raise SessionCommitRejected(FailureCode(error.code)) from error
            if row.version != version:
                raise SessionVersionConflict()
            try:
                candidate = apply_patch(current, patch)
                self.vocabulary.validate(candidate.criteria)
            except ValueError as error:
                raise SessionCommitRejected(FailureCode.SESSION_STATE_INVALID) from error
            now = await _now(conn)
            updated = await conn.scalar(
                update(AISearchSession)
                .where(
                    *self._owned(subject, session_id),
                    AISearchSession.version == version,
                )
                .values(
                    version=candidate.version,
                    criteria=candidate.criteria.model_dump(mode="json", exclude_none=True),
                    updated_at=now,
                    expires_at=now + timedelta(seconds=self.policy.inactivity_seconds),
                )
                .returning(AISearchSession.id)
            )
            if updated is None:
                raise SessionVersionConflict()
            conn.add(
                AISearchResult(
                    id=receipt.result_ref,
                    subject_kind=subject.kind,
                    subject_id=subject.id,
                    idempotency_key=operation.idempotency_key,
                    session_id=session_id,
                    session_version=candidate.version,
                    intent=candidate.model_dump(mode="json", exclude_none=True),
                    intent_hash=intent_hash(candidate),
                    result_count=receipt.count,
                )
            )
            await conn.flush()

        return commit

    async def finalize_patch(
        self, subject: QuotaSubject, operation: QuotaOperation, fence: int, patch: IntentPatch, receipt: ResultReceipt
    ) -> OperationState:
        return await self.ledger.finalize(
            subject, operation, fence, receipt, commit_session=self.commit_patch(subject, operation, patch, receipt)
        )

    async def result(self, subject: QuotaSubject, result_ref: UUID) -> CommittedIntent:
        """Read original normalized result; never regenerate, debit or reapply.

        AI-09 must separately revalidate current listing visibility and cursor
        binding. This table contains no cards or invented matching evidence.
        """
        async with self.ledger.sessions() as conn:
            row = await conn.scalar(
                select(AISearchResult).where(
                    AISearchResult.id == result_ref,
                    AISearchResult.subject_kind == subject.kind,
                    AISearchResult.subject_id == subject.id,
                )
            )
            if row is None:
                raise SessionError("RESULT_NOT_FOUND")
            try:
                await self._read(conn, subject, row.session_id)
            except SessionError as error:
                raise SessionError("RESULT_EXPIRED_REQUERY_REQUIRED") from error
            try:
                intent = SearchIntent.model_validate_json(json.dumps(row.intent))
                self.vocabulary.validate(intent.criteria)
            except (ValueError, TypeError) as error:
                raise SessionError("RESULT_STATE_INVALID") from error
            if (
                intent.session_id != row.session_id
                or intent.version != row.session_version
                or intent_hash(intent) != row.intent_hash
            ):
                raise SessionError("RESULT_STATE_INVALID")
            return CommittedIntent(
                result_ref=row.id, count=row.result_count, intent=intent, intent_hash=row.intent_hash
            )
