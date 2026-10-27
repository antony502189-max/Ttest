"""PG quota transactions. Never call providers or hold a connection across inference."""

from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..models.ai_search_quota import AISearchRequest, AIUsageDay
from ..schemas.ai_search_quota import (
    DailyQuotaView,
    FailureCode,
    LeasePolicy,
    OperationState,
    QuotaOperation,
    QuotaSubject,
    Reservation,
    ResultReceipt,
)

SessionCommit = Callable[[AsyncSession, UUID, int], Awaitable[None]]


class QuotaError(Exception):
    """Stable internal reason code; HTTP mapping belongs to the query API."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class SessionCommitRejected(Exception):
    """A deterministic session failure releases quota after callback rollback."""

    def __init__(self, failure: FailureCode):
        if failure not in {
            FailureCode.SESSION_VERSION_CONFLICT,
            FailureCode.SESSION_EXPIRED,
            FailureCode.SESSION_NOT_FOUND,
            FailureCode.SESSION_STATE_INVALID,
        }:
            raise ValueError("a session failure code is required")
        self.failure = failure
        super().__init__(failure)


class SessionVersionConflict(SessionCommitRejected):
    """The session CAS callback must raise this when its guarded update loses."""

    def __init__(self):
        super().__init__(FailureCode.SESSION_VERSION_CONFLICT)


async def _now(session: AsyncSession) -> datetime:
    value = (await session.execute(select(func.clock_timestamp()))).scalar_one()
    if not isinstance(value, datetime):
        raise QuotaError("LEDGER_INVARIANT_VIOLATION")
    return value


async def madrid_window(session: AsyncSession, at: datetime | None = None) -> tuple[date, datetime]:
    """Use PG's IANA timezone data and clock, independent of host timezone."""
    row = (
        await session.execute(
            text(
                "SELECT d, (d + 1)::timestamp AT TIME ZONE 'Europe/Madrid' FROM "
                "(SELECT (COALESCE(CAST(:at AS timestamptz), clock_timestamp()) "
                "AT TIME ZONE 'Europe/Madrid')::date AS d) AS bucket"
            ),
            {"at": at},
        )
    ).one()
    return row[0], row[1]


class QuotaLedger:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], policy: LeasePolicy):
        self.sessions = sessions
        self.policy = policy

    async def daily_status(self, subject: QuotaSubject) -> DailyQuotaView:
        """One read-only Madrid-day snapshot; no row creation, TTL renewal or recovery."""
        async with self.sessions() as session, session.begin():
            await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            day, reset = await madrid_window(session)
            usage = await session.scalar(select(AIUsageDay).where(*self._day_key(subject, day)))
            limit = usage.quota_limit if usage is not None else 3 if subject.kind == "guest" else 200
            used, reserved = (usage.used, usage.reserved) if usage is not None else (0, 0)
            return DailyQuotaView(madrid_date=day, reset_at=reset, limit=limit, used=used, reserved=reserved,
                                  remaining=limit - used - reserved)

    @staticmethod
    def _key(subject: QuotaSubject, key: UUID):
        return (
            AISearchRequest.subject_kind == subject.kind,
            AISearchRequest.subject_id == subject.id,
            AISearchRequest.idempotency_key == key,
        )

    @staticmethod
    def _day_key(subject: QuotaSubject, day: date):
        return (
            AIUsageDay.subject_kind == subject.kind,
            AIUsageDay.subject_id == subject.id,
            AIUsageDay.madrid_date == day,
        )

    async def _request(self, session: AsyncSession, subject: QuotaSubject, key: UUID, *, lock: bool = False):
        query = select(AISearchRequest).where(*self._key(subject, key)).execution_options(populate_existing=True)
        return await session.scalar(query.with_for_update() if lock else query)

    async def _state(self, session: AsyncSession, request: AISearchRequest) -> OperationState:
        subject = QuotaSubject.model_validate({"kind": request.subject_kind, "id": request.subject_id})
        day = await session.scalar(select(AIUsageDay).where(*self._day_key(subject, request.madrid_date)))
        if day is None:
            raise QuotaError("LEDGER_INVARIANT_VIOLATION")
        reset = await session.scalar(
            text("SELECT (CAST(:day AS date) + 1)::timestamp AT TIME ZONE 'Europe/Madrid'"),
            {"day": request.madrid_date},
        )
        return OperationState.model_validate(
            {
                "idempotency_key": request.idempotency_key,
                "status": request.status,
                "madrid_date": request.madrid_date,
                "fence": request.fence,
                "lease_until": request.lease_until,
                "recover_after": request.recover_after,
                "receipt": None
                if request.result_ref is None
                else {
                    "result_ref": request.result_ref,
                    "count": request.result_count,
                },
                "failure_code": request.failure_code,
                "used": day.used,
                "reserved": day.reserved,
                "limit": day.quota_limit,
                "remaining": day.quota_limit - day.used - day.reserved,
                "reset_at": reset,
            }
        )

    @staticmethod
    def _check_hash(request: AISearchRequest, operation: QuotaOperation) -> None:
        if request.request_hash != operation.fingerprint():
            raise QuotaError("IDEMPOTENCY_CONFLICT")

    async def reserve(self, subject: QuotaSubject, operation: QuotaOperation) -> Reservation:
        async with self.sessions.begin() as session:
            existing = await self._request(session, subject, operation.idempotency_key)
            if existing is not None:
                self._check_hash(existing, operation)
                return Reservation(
                    action="replay" if existing.status in {"succeeded", "failed"} else "inflight",
                    operation=await self._state(session, existing),
                )
            day, _ = await madrid_window(session)
            await session.execute(
                insert(AIUsageDay)
                .values(
                    subject_kind=subject.kind,
                    subject_id=subject.id,
                    madrid_date=day,
                )
                .on_conflict_do_nothing()
            )
            usage = (
                await session.scalars(
                    select(AIUsageDay)
                    .where(
                        *self._day_key(subject, day),
                    )
                    .with_for_update()
                )
            ).one()
            # Recheck after day lock: same-key final-slot race must replay.
            existing = await self._request(session, subject, operation.idempotency_key)
            if existing is None:
                if usage.used + usage.reserved >= usage.quota_limit:
                    raise QuotaError("QUOTA_EXHAUSTED")
                now = await _now(session)
                lease = now + timedelta(seconds=self.policy.reservation_seconds)
                created = await session.scalar(
                    insert(AISearchRequest)
                    .values(
                        subject_kind=subject.kind,
                        subject_id=subject.id,
                        idempotency_key=operation.idempotency_key,
                        request_hash=operation.fingerprint(),
                        madrid_date=day,
                        channel=operation.channel,
                        session_id=operation.session_id,
                        expected_session_version=operation.expected_session_version,
                        status="reserved",
                        lease_until=lease,
                        recover_after=lease + timedelta(seconds=self.policy.recovery_grace_seconds),
                    )
                    .on_conflict_do_nothing()
                    .returning(AISearchRequest)
                )
                if created is not None:
                    usage.reserved += 1
                    await session.flush()
                    return Reservation(action="created", operation=await self._state(session, created))
                # Same key inserted against yesterday's row across midnight.
                existing = await self._request(session, subject, operation.idempotency_key)
            if existing is None:
                raise QuotaError("LEDGER_INVARIANT_VIOLATION")
            self._check_hash(existing, operation)
            return Reservation(
                action="replay" if existing.status in {"succeeded", "failed"} else "inflight",
                operation=await self._state(session, existing),
            )

    async def claim(self, subject: QuotaSubject, operation: QuotaOperation) -> OperationState:
        async with self.sessions.begin() as session:
            request = await self._request(session, subject, operation.idempotency_key, lock=True)
            if request is None:
                raise QuotaError("OPERATION_NOT_FOUND")
            self._check_hash(request, operation)
            now = await _now(session)
            if request.status != "reserved" or request.lease_until <= now:
                raise QuotaError("CLAIM_REJECTED")
            request.status = "running"
            request.fence += 1
            request.lease_until = now + timedelta(seconds=self.policy.running_seconds)
            request.recover_after = request.lease_until + timedelta(seconds=self.policy.recovery_grace_seconds)
            await session.flush()
            return await self._state(session, request)

    async def _locked(self, session: AsyncSession, subject: QuotaSubject, key: UUID):
        request = await self._request(session, subject, key)
        if request is None:
            raise QuotaError("OPERATION_NOT_FOUND")
        # Counter mutators always lock day THEN request. Claim never locks day.
        usage = (
            await session.scalars(
                select(AIUsageDay)
                .where(
                    *self._day_key(subject, request.madrid_date),
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).one()
        request = await self._request(session, subject, key, lock=True)
        if request is None:
            raise QuotaError("LEDGER_INVARIANT_VIOLATION")
        return usage, request

    @staticmethod
    async def _live(session: AsyncSession, request: AISearchRequest, fence: int) -> datetime:
        now = await _now(session)
        if type(fence) is not int or request.fence != fence or request.lease_until <= now:
            raise QuotaError("STALE_WORKER")
        return now

    async def _complete(
        self,
        session: AsyncSession,
        usage: AIUsageDay,
        request: AISearchRequest,
        now: datetime,
        receipt: ResultReceipt | None,
        failure: FailureCode | None,
    ) -> OperationState:
        usage.reserved -= 1
        if receipt is not None:
            usage.used += 1
            request.status = "succeeded"
            request.result_ref, request.result_count = receipt.result_ref, receipt.count
        else:
            request.status = "failed"
            request.failure_code = failure
        request.completed_at = now
        await session.flush()
        return await self._state(session, request)

    async def finalize_in_transaction(
        self,
        session: AsyncSession,
        subject: QuotaSubject,
        operation: QuotaOperation,
        fence: int,
        receipt: ResultReceipt,
        *,
        commit_session: SessionCommit,
    ) -> OperationState:
        """AI-08 hook: CAS + durable result reference + debit, one PG transaction.

        Callback must use only this session/transaction, validate ownership, and
        perform a guarded session CAS plus durable result write. No network,
        commit or rollback inside callback. Terminal replay never invokes it.
        """
        if not session.in_transaction():
            raise ValueError("finalize requires an explicit enclosing transaction")
        usage, request = await self._locked(session, subject, operation.idempotency_key)
        self._check_hash(request, operation)
        if request.status in {"succeeded", "failed"}:
            return await self._state(session, request)
        now = await self._live(session, request, fence)
        if request.status != "running":
            raise QuotaError("STALE_WORKER")
        try:
            # Roll back any callback-local writes if its CAS conflicts.
            async with session.begin_nested():
                await commit_session(session, request.session_id, request.expected_session_version)
                # Keep the late lease check and all success writes inside the
                # savepoint too: even a caller catching the error must not be
                # able to commit a session CAS without its quota debit.
                now = await self._live(session, request, fence)
                result = await self._complete(session, usage, request, now, receipt, None)
            return result
        except SessionCommitRejected as error:
            return await self._complete(session, usage, request, now, None, error.failure)

    async def finalize(
        self,
        subject: QuotaSubject,
        operation: QuotaOperation,
        fence: int,
        receipt: ResultReceipt,
        *,
        commit_session: SessionCommit,
    ) -> OperationState:
        async with self.sessions.begin() as session:
            return await self.finalize_in_transaction(
                session, subject, operation, fence, receipt, commit_session=commit_session
            )

    async def release(
        self, subject: QuotaSubject, operation: QuotaOperation, fence: int, failure: FailureCode
    ) -> OperationState:
        if not isinstance(failure, FailureCode):
            raise TypeError("explicit failure code required; clarification policy is unresolved")
        async with self.sessions.begin() as session:
            usage, request = await self._locked(session, subject, operation.idempotency_key)
            self._check_hash(request, operation)
            if request.status in {"succeeded", "failed"}:
                return await self._state(session, request)
            now = await self._live(session, request, fence)
            return await self._complete(session, usage, request, now, None, failure)

    async def recover(self, subject: QuotaSubject, key: UUID) -> OperationState:
        """Release an expired operation after grace; never reclaim/infer again."""
        async with self.sessions.begin() as session:
            usage, request = await self._locked(session, subject, key)
            if request.status in {"succeeded", "failed"}:
                return await self._state(session, request)
            now = await _now(session)
            if request.recover_after > now:
                raise QuotaError("RECOVERY_NOT_DUE")
            request.fence += 1
            return await self._complete(session, usage, request, now, None, FailureCode.LEASE_EXPIRED)

    async def recover_expired(self, batch_size: int = 100) -> list[OperationState]:
        if type(batch_size) is not int or not 1 <= batch_size <= 100:
            raise ValueError("recovery batch must be between 1 and 100")
        async with self.sessions() as session:
            candidates = (
                await session.execute(
                    select(
                        AISearchRequest.subject_kind,
                        AISearchRequest.subject_id,
                        AISearchRequest.idempotency_key,
                    )
                    .where(
                        AISearchRequest.status.in_(("reserved", "running")),
                        AISearchRequest.recover_after <= func.clock_timestamp(),
                    )
                    .order_by(AISearchRequest.recover_after)
                    .limit(batch_size)
                )
            ).all()
        recovered = []
        for kind, subject_id, key in candidates:
            subject = QuotaSubject.model_validate({"kind": kind, "id": subject_id})
            try:
                recovered.append(await self.recover(subject, key))
            except QuotaError as error:
                if error.code != "RECOVERY_NOT_DUE":
                    raise
        return recovered
