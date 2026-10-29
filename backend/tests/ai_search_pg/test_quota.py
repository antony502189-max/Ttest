"""Real PG tests for the actual backend migration/repository, no application DSN."""

import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import MetaData, func, select, text, update
from sqlalchemy.exc import IntegrityError

from app.models.ai_search_quota import AISearchRequest, AIUsageDay
from app.models.ai_search_session import AISearchResult, AISearchSession, AISessionCommand
from app.repositories.ai_search_quota import QuotaError, QuotaLedger, SessionVersionConflict, madrid_window
from app.schemas.ai_search_quota import FailureCode, LeasePolicy, QuotaOperation, QuotaSubject, ResultReceipt
from app.services.ai_search_attempts import AIAttemptGate, AIAttemptRejected
from app.services.rate_limit import RedisRateLimiter

pytestmark = pytest.mark.integration


def operation(**changes):
    return QuotaOperation(
        **{
            "idempotency_key": uuid4(),
            "channel": "text",
            "payload_sha256": "a" * 64,
            "session_id": uuid4(),
            "expected_session_version": 0,
            **changes,
        }
    )


async def writer(pg, subject, op, receipt):
    """AI-08 stand-in: real guarded SQL CAS + durable synthetic result write."""
    _, sessions = pg
    async with sessions.begin() as conn:
        await conn.execute(
            text("INSERT INTO session_fixture VALUES (:id,:owner,0) ON CONFLICT DO NOTHING"),
            {"id": op.session_id, "owner": subject.id},
        )

    async def commit(conn, session_id, expected_version):
        found = await conn.scalar(
            text(
                "UPDATE session_fixture SET version=version+1 "
                "WHERE id=:id AND owner=:owner AND version=:version RETURNING version"
            ),
            {"id": session_id, "owner": subject.id, "version": expected_version},
        )
        if found is None:
            raise SessionVersionConflict()
        await conn.execute(
            text("INSERT INTO result_fixture VALUES (:id,:count)"), {"id": receipt.result_ref, "count": receipt.count}
        )

    return commit


async def counts(pg, subject):
    async with pg[1]() as conn:
        return (
            await conn.execute(
                select(func.sum(AIUsageDay.used), func.sum(AIUsageDay.reserved)).where(
                    AIUsageDay.subject_kind == subject.kind,
                    AIUsageDay.subject_id == subject.id,
                )
            )
        ).one()


async def expire(pg, op, *, grace=True):
    async with pg[1].begin() as conn:
        await conn.execute(
            update(AISearchRequest)
            .where(AISearchRequest.idempotency_key == op.idempotency_key)
            .values(
                lease_until=func.clock_timestamp() - text("interval '1 second'"),
                recover_after=func.clock_timestamp()
                + text("interval '-1 second'" if grace else "interval '30 seconds'"),
            )
        )


@pytest.mark.parametrize("kind,limit", [("guest", 3), ("auth", 200)])
async def test_exact_limits_and_reserved_capacity(pg, kind, limit):
    ledger, _ = pg
    subject = QuotaSubject(kind=kind, id=uuid4())
    for _ in range(limit):
        await ledger.reserve(subject, operation())
    with pytest.raises(QuotaError, match="QUOTA_EXHAUSTED"):
        await ledger.reserve(subject, operation())
    assert await counts(pg, subject) == (0, limit)


async def test_voice_text_zero_success_and_terminal_replay(pg):
    ledger, _ = pg
    subject = QuotaSubject(kind="guest", id=uuid4())
    for channel in ("text", "voice", "text"):
        op, receipt = operation(channel=channel), ResultReceipt(result_ref=uuid4(), count=0)
        assert (await ledger.reserve(subject, op)).action == "created"
        assert (await ledger.reserve(subject, op)).action == "inflight"
        claimed = await ledger.claim(subject, op)
        commit = await writer(pg, subject, op, receipt)
        result = await ledger.finalize(subject, op, claimed.fence, receipt, commit_session=commit)
        assert result.receipt == receipt
        assert (await ledger.reserve(subject, op)).operation == result
        assert await ledger.finalize(subject, op, claimed.fence, receipt, commit_session=commit) == result
        with pytest.raises(QuotaError, match="CLAIM_REJECTED"):
            await ledger.claim(subject, op)
    with pytest.raises(QuotaError, match="QUOTA_EXHAUSTED"):
        await ledger.reserve(subject, operation(channel="voice"))
    assert await counts(pg, subject) == (3, 0)


@pytest.mark.parametrize("failure", [FailureCode.ASR_FAILURE, FailureCode.LLM_FAILURE, FailureCode.BACKEND_FAILURE])
async def test_failure_release_and_no_reopen(pg, failure):
    ledger, _ = pg
    subject, op = QuotaSubject(kind="guest", id=uuid4()), operation()
    await ledger.reserve(subject, op)
    worker = await ledger.claim(subject, op)
    failed = await ledger.release(subject, op, worker.fence, failure)
    assert await ledger.release(subject, op, worker.fence, failure) == failed
    assert (await ledger.reserve(subject, op)).action == "replay"
    assert await counts(pg, subject) == (0, 0)


async def test_release_before_claim_and_subject_hash_isolation(pg):
    ledger, _ = pg
    subject, op = QuotaSubject(kind="guest", id=uuid4()), operation()
    await ledger.reserve(subject, op)
    for changed in (
        {"channel": "voice"},
        {"payload_sha256": "b" * 64},
        {"session_id": uuid4()},
        {"expected_session_version": 1},
    ):
        with pytest.raises(QuotaError, match="IDEMPOTENCY_CONFLICT"):
            await ledger.reserve(subject, op.model_copy(update=changed))
        with pytest.raises(QuotaError, match="IDEMPOTENCY_CONFLICT"):
            await ledger.claim(subject, op.model_copy(update=changed))
    assert (await ledger.reserve(QuotaSubject(kind="auth", id=subject.id), op)).action == "created"
    assert (await ledger.reserve(QuotaSubject(kind="guest", id=uuid4()), op)).action == "created"
    await ledger.release(subject, op, 0, FailureCode.ATTEMPT_LIMIT)
    assert await counts(pg, subject) == (0, 0)


@pytest.mark.parametrize("same_key", [True, False])
async def test_concurrent_last_slot(pg, same_key):
    ledger, _ = pg
    subject, op = QuotaSubject(kind="guest", id=uuid4()), operation()
    await ledger.reserve(subject, operation())
    await ledger.reserve(subject, operation())
    barrier = asyncio.Barrier(12)

    async def race():
        await barrier.wait()
        try:
            return (await ledger.reserve(subject, op if same_key else operation())).action
        except QuotaError as error:
            assert error.code == "QUOTA_EXHAUSTED"
            return "quota"

    results = await asyncio.gather(*(race() for _ in range(12)))
    assert results.count("created") == 1
    assert results.count("inflight" if same_key else "quota") == 11
    assert await counts(pg, subject) == (0, 3)


async def test_one_worker_and_concurrent_atomic_finalize(pg):
    ledger, sessions = pg
    subject, op = QuotaSubject(kind="guest", id=uuid4()), operation()
    await ledger.reserve(subject, op)

    async def claim():
        try:
            return (await ledger.claim(subject, op)).fence
        except QuotaError as error:
            assert error.code == "CLAIM_REJECTED"
            return None

    assert (await asyncio.gather(*(claim() for _ in range(8)))).count(1) == 1
    receipt = ResultReceipt(result_ref=uuid4(), count=2)
    commit = await writer(pg, subject, op, receipt)
    results = await asyncio.gather(*(ledger.finalize(subject, op, 1, receipt, commit_session=commit) for _ in range(8)))
    assert all(result == results[0] for result in results)
    assert await counts(pg, subject) == (1, 0)
    async with sessions() as conn:
        assert await conn.scalar(text("SELECT version FROM session_fixture")) == 1
        assert await conn.scalar(text("SELECT count(*) FROM result_fixture")) == 1


async def test_session_cas_conflict_releases_and_rollback_is_atomic(pg):
    ledger, sessions = pg
    subject, first = QuotaSubject(kind="guest", id=uuid4()), operation()
    second = operation(session_id=first.session_id)
    receipt = ResultReceipt(result_ref=uuid4(), count=0)
    commit = await writer(pg, subject, first, receipt)
    for op in (first, second):
        await ledger.reserve(subject, op)
        await ledger.claim(subject, op)
    # Outer rollback includes CAS, durable result, counters and terminal status.
    async with sessions() as conn, conn.begin():
        await ledger.finalize_in_transaction(conn, subject, first, 1, receipt, commit_session=commit)
        await conn.rollback()
    assert await counts(pg, subject) == (0, 2)
    async with sessions() as conn:
        assert await conn.scalar(text("SELECT version FROM session_fixture")) == 0
        assert await conn.scalar(text("SELECT count(*) FROM result_fixture")) == 0
    await ledger.finalize(subject, first, 1, receipt, commit_session=commit)
    conflict = await ledger.finalize(subject, second, 1, receipt, commit_session=commit)
    assert conflict.failure_code == "SESSION_VERSION_CONFLICT"
    assert await counts(pg, subject) == (1, 0)


async def test_cas_exception_rolls_back_partial_callback_writes(pg):
    ledger, sessions = pg
    subject, op = QuotaSubject(kind="guest", id=uuid4()), operation()
    await ledger.reserve(subject, op)
    await ledger.claim(subject, op)
    receipt = ResultReceipt(result_ref=uuid4(), count=1)
    commit = await writer(pg, subject, op, receipt)

    async def fail_after_write(conn, sid, version):
        await commit(conn, sid, version)
        raise SessionVersionConflict()

    result = await ledger.finalize(subject, op, 1, receipt, commit_session=fail_after_write)
    assert result.status == "failed" and result.failure_code == "SESSION_VERSION_CONFLICT"
    assert await counts(pg, subject) == (0, 0)
    async with sessions() as conn:
        assert await conn.scalar(text("SELECT version FROM session_fixture")) == 0
        assert await conn.scalar(text("SELECT count(*) FROM result_fixture")) == 0


@pytest.mark.parametrize("running", [False, True])
async def test_crash_grace_recovery_and_fencing(pg, running):
    ledger, _ = pg
    subject, op = QuotaSubject(kind="guest", id=uuid4()), operation()
    await ledger.reserve(subject, op)
    if running:
        await ledger.claim(subject, op)
    await expire(pg, op, grace=False)
    with pytest.raises(QuotaError, match="RECOVERY_NOT_DUE"):
        await ledger.recover(subject, op.idempotency_key)
    with pytest.raises(QuotaError, match="STALE_WORKER"):
        await ledger.release(subject, op, int(running), FailureCode.BACKEND_FAILURE)
    await expire(pg, op)
    result = await ledger.recover(subject, op.idempotency_key)
    assert result.fence == int(running) + 1
    assert result.failure_code == "LEASE_EXPIRED"
    assert (await ledger.reserve(subject, op)).action == "replay"
    assert await counts(pg, subject) == (0, 0)
    with pytest.raises(QuotaError, match="CLAIM_REJECTED"):
        await ledger.claim(subject, op)


async def test_late_finalize_vs_recovery(pg):
    ledger, _ = pg
    subject, op = QuotaSubject(kind="guest", id=uuid4()), operation()
    await ledger.reserve(subject, op)
    await ledger.claim(subject, op)
    receipt = ResultReceipt(result_ref=uuid4(), count=1)
    commit = await writer(pg, subject, op, receipt)
    await expire(pg, op)

    async def race(recover):
        try:
            if recover:
                return (await ledger.recover(subject, op.idempotency_key)).status
            return (await ledger.finalize(subject, op, 1, receipt, commit_session=commit)).status
        except QuotaError as error:
            assert error.code == "STALE_WORKER"
            return "stale"

    results = await asyncio.gather(*(race(index % 2) for index in range(12)))
    assert "succeeded" not in results
    assert await counts(pg, subject) == (0, 0)


async def test_midnight_bucket_immutable_and_new_day_available(pg):
    ledger, sessions = pg
    subject, op = QuotaSubject(kind="guest", id=uuid4()), operation()
    await ledger.reserve(subject, op)
    await ledger.claim(subject, op)
    async with sessions.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO ai_usage_days(subject_kind,subject_id,madrid_date,reserved) "
                "SELECT subject_kind,subject_id,madrid_date-1,1 FROM ai_usage_days"
            )
        )
        await conn.execute(text("UPDATE ai_search_requests SET madrid_date=madrid_date-1"))
        await conn.execute(
            text(
                "UPDATE ai_usage_days SET reserved=0 WHERE madrid_date="
                "(clock_timestamp() AT TIME ZONE 'Europe/Madrid')::date"
            )
        )
    receipt = ResultReceipt(result_ref=uuid4(), count=0)
    commit = await writer(pg, subject, op, receipt)
    completed = await ledger.finalize(subject, op, 1, receipt, commit_session=commit)
    assert (await ledger.reserve(subject, op)).action == "replay"
    new = await ledger.reserve(subject, operation())
    assert new.operation.madrid_date > completed.madrid_date
    assert (completed.used, completed.reserved, new.operation.used, new.operation.reserved) == (1, 0, 0, 1)


@pytest.mark.parametrize(
    "start,end,hours",
    [
        ("2026-03-28T23:00:00+00:00", "2026-03-29T22:00:00+00:00", 23),
        ("2026-10-24T22:00:00+00:00", "2026-10-25T23:00:00+00:00", 25),
        ("2026-10-25T23:00:00+00:00", "2026-10-26T23:00:00+00:00", 24),
    ],
)
async def test_madrid_dst(pg, start, end, hours):
    async with pg[1]() as conn:
        day, reset = await madrid_window(conn, datetime.fromisoformat(start))
    assert reset.astimezone(UTC) == datetime.fromisoformat(end)
    assert (reset - datetime.fromisoformat(start)).total_seconds() == hours * 3600
    assert day == datetime.fromisoformat(end).date()


async def test_bounded_reconciler(pg):
    ledger, _ = pg
    subject = QuotaSubject(kind="guest", id=uuid4())
    for _ in range(3):
        op = operation()
        await ledger.reserve(subject, op)
        await expire(pg, op)
    assert len(await ledger.recover_expired(2)) == 2
    assert await counts(pg, subject) == (0, 1)
    assert len(await ledger.recover_expired()) == 1
    assert await ledger.recover_expired() == []
    assert await counts(pg, subject) == (0, 0)


async def test_actual_migration_matches_models(pg):
    async with pg[1]() as conn:
        metadata = MetaData()
        for model in (AIUsageDay, AISearchRequest, AISearchSession, AISearchResult, AISessionCommand):
            model.__table__.to_metadata(metadata)

        def compare(sync):
            context = MigrationContext.configure(
                sync.connection(),
                opts={
                    "include_object": lambda obj, name, kind, reflected, compare_to: (
                        kind != "table" or name not in {"session_fixture", "result_fixture"}
                    ),
                },
            )
            return compare_metadata(context, metadata)

        differences = await conn.run_sync(compare)
    assert differences == []


async def test_deadline_expiry_during_session_lock_rolls_back_cas(pg):
    _, sessions = pg
    ledger = QuotaLedger(sessions, LeasePolicy(reservation_seconds=60, running_seconds=1, recovery_grace_seconds=0))
    subject, op = QuotaSubject(kind="guest", id=uuid4()), operation()
    receipt = ResultReceipt(result_ref=uuid4(), count=1)
    commit = await writer(pg, subject, op, receipt)
    await ledger.reserve(subject, op)
    await ledger.claim(subject, op)

    async def slow_sql(conn, sid, version):
        # Simulate a DB lock wait after the first lease check, not provider I/O.
        await conn.execute(text("SELECT pg_sleep(1.1)"))
        await commit(conn, sid, version)

    # Catch the error INSIDE the outer transaction and commit it. The ledger
    # savepoint must still undo the expired worker's session/result writes.
    async with sessions.begin() as conn:
        with pytest.raises(QuotaError, match="STALE_WORKER"):
            await ledger.finalize_in_transaction(conn, subject, op, 1, receipt, commit_session=slow_sql)
    async with sessions() as conn:
        assert await conn.scalar(text("SELECT version FROM session_fixture")) == 0
        assert await conn.scalar(text("SELECT count(*) FROM result_fixture")) == 0
    assert await counts(pg, subject) == (0, 1)
    await ledger.recover(subject, op.idempotency_key)
    assert await counts(pg, subject) == (0, 0)


async def test_database_bounds_and_stale_fence_are_fail_closed(pg):
    ledger, sessions = pg
    subject, op = QuotaSubject(kind="guest", id=uuid4()), operation()
    await ledger.reserve(subject, op)
    await ledger.claim(subject, op)
    with pytest.raises(QuotaError, match="STALE_WORKER"):
        await ledger.release(subject, op, 0, FailureCode.BACKEND_FAILURE)
    for changes in ({"used": 3}, {"used": -1}, {"reserved": -1}):
        with pytest.raises(IntegrityError):
            async with sessions.begin() as conn:
                await conn.execute(update(AIUsageDay).values(**changes))
    assert await counts(pg, subject) == (0, 1)


async def test_real_redis_attempt_budget_shared_voice_text_namespace():
    value = os.getenv("AI_QUOTA_REDIS_TEST_URL") or os.getenv("REDIS_URL")
    if not value:
        pytest.skip("local Redis not configured; dedicated CI requires Redis")
    from urllib.parse import urlsplit

    if urlsplit(value).hostname not in {"127.0.0.1", "localhost", "::1"}:
        pytest.fail("Redis test must use a disposable loopback Redis instance")
    limiter = RedisRateLimiter(value)
    try:
        gate = AIAttemptGate(limiter, attempts=2, window_seconds=60)
        subject = QuotaSubject(kind="guest", id=uuid4())
        await gate.check(subject)
        await gate.check(subject)
        with pytest.raises(AIAttemptRejected, match="ATTEMPT_LIMIT"):
            await gate.check(subject)
        await gate.check(QuotaSubject(kind="auth", id=subject.id))
    finally:
        await limiter.close()
