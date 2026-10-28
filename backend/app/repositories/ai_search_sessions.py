"""AI-08: normalized PG sessions and the real AI-07 finalize callback."""

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.ai_search_quota import AISearchRequest
from ..models.ai_search_session import AISearchResult, AISearchSession, AISessionCommand
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
    def __init__(self, code: str, retry_after: int = 0):
        self.code = code
        self.retry_after = retry_after
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

    async def _create(self, conn: AsyncSession, subject: QuotaSubject, *, max_active: int | None = None) -> SessionSnapshot:
        if max_active is not None and (type(max_active) is not int or max_active < 1):
            raise ValueError("explicit positive active session bound required")
        await conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                           {"key": f"ai-session-create:{subject.kind}:{subject.id}"})
        now = await _now(conn)
        if max_active is not None:
            active = select(func.count(), func.min(AISearchSession.expires_at)).where(
                AISearchSession.subject_kind == subject.kind, AISearchSession.subject_id == subject.id,
                AISearchSession.closed_at.is_(None), AISearchSession.expires_at > now)
            count, earliest = (await conn.execute(active)).one()
            if count >= max_active:
                raise SessionError("SESSION_LIMIT", max(1, math.ceil((earliest - now).total_seconds())))
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

    async def _command(self, conn: AsyncSession, subject: QuotaSubject, key: UUID | None,
                       action: str, source_id: UUID | None = None,
                       expected_version: int | None = None) -> SessionSnapshot | None:
        # One lock order for create/reset, including legacy callers. Serialize
        # before reading either command or source row to avoid cap/lock races.
        await conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                           {"key": f"ai-session-create:{subject.kind}:{subject.id}"})
        if key is None:
            return None
        if not isinstance(key, UUID):
            raise TypeError("UUID session command key required")
        command = await conn.get(AISessionCommand, (subject.kind, subject.id, key))
        if command is None:
            return None
        if (command.action, command.source_id, command.expected_version) != (action, source_id, expected_version):
            raise SessionError("SESSION_COMMAND_CONFLICT")
        row, intent = await self._read(conn, subject, command.result_id)
        return SessionSnapshot(intent=intent, expires_at=row.expires_at)

    @staticmethod
    def _remember(conn: AsyncSession, subject: QuotaSubject, key: UUID | None,
                  snapshot: SessionSnapshot, action: str, source_id: UUID | None = None,
                  expected_version: int | None = None) -> None:
        if key is not None:
            conn.add(AISessionCommand(subject_kind=subject.kind, subject_id=subject.id,
                idempotency_key=key, action=action, source_id=source_id, expected_version=expected_version,
                result_id=snapshot.intent.session_id))

    async def create(self, subject: QuotaSubject, *, max_active: int | None = None,
                     idempotency_key: UUID | None = None) -> SessionSnapshot:
        async with self.ledger.sessions.begin() as conn:
            replay = await self._command(conn, subject, idempotency_key, "create")
            if replay is not None:
                return replay
            snapshot = await self._create(conn, subject, max_active=max_active)
            self._remember(conn, subject, idempotency_key, snapshot, "create")
            return snapshot

    async def get(self, subject: QuotaSubject, session_id: UUID) -> SessionSnapshot:
        async with self.ledger.sessions() as conn:
            row, intent = await self._read(conn, subject, session_id)
            return SessionSnapshot(intent=intent, expires_at=row.expires_at)

    async def reset(self, subject: QuotaSubject, session_id: UUID, expected_version: int, *, max_active: int | None = None,
                    idempotency_key: UUID | None = None) -> SessionSnapshot:
        """Explicit caller command only. Never inferred from missing patch fields."""
        if type(expected_version) is not int or not 0 <= expected_version <= 2_147_483_647:
            raise ValueError("a bounded expected version is required")
        async with self.ledger.sessions.begin() as conn:
            replay = await self._command(conn, subject, idempotency_key, "reset", session_id, expected_version)
            if replay is not None:
                return replay
            row, _ = await self._read(conn, subject, session_id, lock=True, allow_expired=True)
            if row.closed_at is not None or row.version != expected_version:
                raise SessionError("SESSION_VERSION_CONFLICT")
            row.updated_at = await _now(conn)
            row.expires_at = row.updated_at
            row.closed_at = row.updated_at
            # New identity; old requests can never resurrect or mutate it.
            snapshot = await self._create(conn, subject, max_active=max_active)
            self._remember(conn, subject, idempotency_key, snapshot, "reset", session_id, expected_version)
            return snapshot

    async def cleanup_unused(self, *, older_than: datetime, limit: int) -> int:
        """Explicit offline retention cutoff only; no worker or default policy.

        Preserve every quota/audit/result row and any session referenced by one.
        Expiry alone is not authorization to run this against application data.
        """
        if older_than.tzinfo is None or type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("aware retention cutoff and bounded batch required")
        async with self.ledger.sessions.begin() as conn:
            now = await _now(conn)
            if older_than > now:
                raise ValueError("retention cutoff cannot be in the future")
            referenced = select(AISearchRequest.idempotency_key).where(AISearchRequest.session_id == AISearchSession.id).exists()
            results = select(AISearchResult.id).where(AISearchResult.session_id == AISearchSession.id).exists()
            commands = select(AISessionCommand.idempotency_key).where(
                (AISessionCommand.result_id == AISearchSession.id) |
                (AISessionCommand.source_id == AISearchSession.id)).exists()
            ids = list(await conn.scalars(select(AISearchSession.id).where(
                AISearchSession.expires_at <= older_than, AISearchSession.version == 0,
                AISearchSession.criteria == {}, ~referenced, ~results, ~commands,
            ).order_by(AISearchSession.expires_at, AISearchSession.id).limit(limit).with_for_update(skip_locked=True)))
            if ids:
                await conn.execute(delete(AISearchSession).where(AISearchSession.id.in_(ids)))
            return len(ids)

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
