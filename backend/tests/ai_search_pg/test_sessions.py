"""Actual session CAS, receipt and quota atomicity on disposable PostgreSQL."""

import asyncio
import json
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError

from app.models.ai_search_quota import AISearchRequest, AIUsageDay
from app.models.ai_search_session import AISearchResult, AISearchSession
from app.repositories.ai_search_quota import QuotaError, QuotaLedger
from app.repositories.ai_search_sessions import SearchSessions, SessionError
from app.schemas.ai_search_intent import IntentPatch, SessionCreate
from app.schemas.ai_search_quota import FailureCode, LeasePolicy, QuotaOperation, QuotaSubject, ResultReceipt

pytestmark = pytest.mark.integration


def hard(value):
    return {"strength": "hard", "value": value}



def operation(snapshot):
    return QuotaOperation(
        idempotency_key=uuid4(),
        channel="text",
        payload_sha256="a" * 64,
        session_id=snapshot.intent.session_id,
        expected_session_version=snapshot.intent.version,
    )


def patch(snapshot, changes=None, remove=()):
    return IntentPatch.model_validate_json(
        json.dumps(
            {
                "schema_version": "ai-search.v1",
                "session_id": str(snapshot.intent.session_id),
                "expected_version": snapshot.intent.version,
                "set": changes or {},
                "remove": list(remove),
            }
        )
    )


async def prepare(store, subject, snapshot):
    op = operation(snapshot)
    await store.ledger.reserve(subject, op)
    await store.ledger.claim(subject, op)
    return op


async def complete(store, subject, snapshot, changes=None, remove=(), receipt=None):
    op = await prepare(store, subject, snapshot)
    receipt = receipt or ResultReceipt(result_ref=uuid4(), count=0)
    result = await store.finalize_patch(subject, op, 1, patch(snapshot, changes, remove), receipt)
    return op, receipt, result


async def usage(pg, subject):
    async with pg[1]() as conn:
        return (
            await conn.execute(
                select(func.sum(AIUsageDay.used), func.sum(AIUsageDay.reserved)).where(
                    AIUsageDay.subject_kind == subject.kind,
                    AIUsageDay.subject_id == subject.id,
                )
            )
        ).one()


async def test_owned_sessions_and_reads_do_not_renew_ttl(store):
    subject = QuotaSubject(kind="guest", id=uuid4())
    initial = await store.create(subject)
    assert initial.intent.version == 0
    assert initial.intent.criteria.model_dump(exclude_none=True) == {}
    assert await store.get(subject, initial.intent.session_id) == initial
    for other in (QuotaSubject(kind="auth", id=subject.id), QuotaSubject(kind="guest", id=uuid4())):
        with pytest.raises(SessionError, match="SESSION_NOT_FOUND"):
            await store.get(other, initial.intent.session_id)
        with pytest.raises(SessionError, match="SESSION_NOT_FOUND"):
            await store.reset(other, initial.intent.session_id, 0)


@pytest.mark.parametrize("mode", ["long", "holiday"])
async def test_explicit_mode_seeds_only_new_session_and_survives_followup(store, pg, mode):
    subject = QuotaSubject(kind="guest", id=uuid4())
    original = await store.create(subject)
    seeded = await store.create(subject, SessionCreate(rental_mode=mode))
    assert seeded.intent.criteria.model_dump(exclude_none=True) == {"rental_mode": hard(mode)}
    assert await store.get(subject, seeded.intent.session_id) == seeded
    assert await store.get(subject, original.intent.session_id) == original
    assert await usage(pg, subject) == (None, None)
    _, receipt, state = await complete(store, subject, seeded, {"balcony": hard(False)})
    assert state.status == "succeeded"
    committed = await store.result(subject, receipt.result_ref)
    assert committed.intent.criteria.rental_mode.value == mode
    assert committed.intent.criteria.balcony.value is False
    reset = await store.reset(subject, seeded.intent.session_id, 1)
    assert reset.intent.criteria.model_dump(exclude_none=True) == {}


async def test_explicit_mode_does_not_bypass_reviewed_active_session_bound(store):
    subject = QuotaSubject(kind="guest", id=uuid4())
    first = await store.create(subject, SessionCreate(rental_mode="holiday"), max_active=1)
    with pytest.raises(SessionError, match="SESSION_LIMIT"):
        await store.create(subject, SessionCreate(rental_mode="long"), max_active=1)
    assert await store.get(subject, first.intent.session_id) == first


async def test_finalize_never_transfers_guest_session_to_another_subject(store, pg):
    owner = QuotaSubject(kind="guest", id=uuid4())
    initial = await store.create(owner)
    for intruder in (QuotaSubject(kind="auth", id=owner.id), QuotaSubject(kind="guest", id=uuid4())):
        _, _, result = await complete(store, intruder, initial, {"balcony": hard(True)})
        assert result.failure_code == "SESSION_NOT_FOUND"
        assert await usage(pg, intruder) == (0, 0)
    assert await store.get(owner, initial.intent.session_id) == initial


async def test_followup_chain_persists_without_dropping_criteria(store, pg):
    subject = QuotaSubject(kind="auth", id=uuid4())
    state = await store.create(subject)
    initial = {
        "budget": hard({"amount": "650.00", "currency": "EUR", "period": "monthly"}),
        "party": hard({"adults": 2, "children": 0, "relationship": "couple"}),
        "pets": hard([{"species": "dog", "size": "small", "count": 1}]),
        "geography": hard({"province_code": "38", "municipality_code": "38001"}),
    }
    changes = (
        initial,
        {"balcony": hard(True)},
        {
            "budget": hard(
                {
                    "amount": "700.00",
                    "currency": "EUR",
                    "period": "monthly",
                }
            )
        },
        {},
    )
    for index, fields in enumerate(changes):
        _, _, result = await complete(store, subject, state, fields, ("balcony",) if index == 3 else ())
        assert result.status == "succeeded"
        next_state = await store.get(subject, state.intent.session_id)
        assert next_state.intent.version == index + 1
        state = next_state
    assert state.intent.criteria.budget.value.amount == "700.00"
    assert state.intent.criteria.balcony is None
    assert state.intent.criteria.party.value.adults == 2
    assert state.intent.criteria.pets.value[0].species == "dog"
    assert state.intent.criteria.geography.value.municipality_code == "38001"
    assert await usage(pg, subject) == (4, 0)


@pytest.mark.parametrize("across_midnight", [False, True])
async def test_two_v7_patches_commit_one_v8_and_one_debit(store, pg, across_midnight):
    subject = QuotaSubject(kind="guest", id=uuid4())
    initial = await store.create(subject)
    async with pg[1].begin() as conn:
        await conn.execute(update(AISearchSession).values(version=7))  # Synthetic initial revision.
    initial = await store.get(subject, initial.intent.session_id)
    first, second = await prepare(store, subject, initial), await prepare(store, subject, initial)
    if across_midnight:
        # Separate day locks ensure it is the real session CAS that arbitrates.
        async with pg[1].begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO ai_usage_days(subject_kind,subject_id,madrid_date,reserved) "
                    "SELECT subject_kind,subject_id,madrid_date-1,1 FROM ai_usage_days"
                )
            )
            await conn.execute(
                update(AISearchRequest)
                .where(AISearchRequest.idempotency_key == first.idempotency_key)
                .values(madrid_date=AISearchRequest.madrid_date - 1)
            )
            await conn.execute(
                text(
                    "UPDATE ai_usage_days SET reserved=1 WHERE madrid_date="
                    "(clock_timestamp() AT TIME ZONE 'Europe/Madrid')::date"
                )
            )
    barrier = asyncio.Barrier(2)

    async def race(op, field):
        await barrier.wait()
        return await store.finalize_patch(
            subject, op, 1, patch(initial, {field: hard(True)}), ResultReceipt(result_ref=uuid4(), count=0)
        )

    results = await asyncio.gather(race(first, "balcony"), race(second, "terrace"))
    assert sorted(r.status for r in results) == ["failed", "succeeded"]
    assert next(r for r in results if r.status == "failed").failure_code == "SESSION_VERSION_CONFLICT"
    current = await store.get(subject, initial.intent.session_id)
    assert current.intent.version == 8
    assert len(current.intent.criteria.model_dump(exclude_none=True)) == 1
    assert await usage(pg, subject) == (1, 0)
    async with pg[1]() as conn:
        assert await conn.scalar(select(func.count()).select_from(AISearchResult)) == 1


async def test_outer_rollback_undoes_real_session_result_and_debit(store, pg):
    subject = QuotaSubject(kind="guest", id=uuid4())
    initial = await store.create(subject)
    op = await prepare(store, subject, initial)
    receipt = ResultReceipt(result_ref=uuid4(), count=2)
    callback = store.commit_patch(subject, op, patch(initial, {"balcony": hard(True)}), receipt)
    async with pg[1]() as conn, conn.begin():
        await store.ledger.finalize_in_transaction(conn, subject, op, 1, receipt, commit_session=callback)
        await conn.rollback()  # Crash before commit / connection loss.
    assert await store.get(subject, initial.intent.session_id) == initial
    assert await usage(pg, subject) == (0, 1)
    async with pg[1]() as conn:
        assert await conn.scalar(select(func.count()).select_from(AISearchResult)) == 0
    result = await store.finalize_patch(subject, op, 1, patch(initial, {"balcony": hard(True)}), receipt)
    assert result.status == "succeeded"
    assert await usage(pg, subject) == (1, 0)


async def test_replay_returns_original_intent_without_reapplying_patch(store, pg):
    subject = QuotaSubject(kind="guest", id=uuid4())
    initial = await store.create(subject)
    op, receipt, committed = await complete(store, subject, initial, {"balcony": hard(True)})
    original_result = await store.result(subject, receipt.result_ref)
    current = await store.get(subject, initial.intent.session_id)
    await complete(store, subject, current, {"terrace": hard(True)})
    replay = await store.finalize_patch(
        subject, op, 1, patch(initial, {"furnished": hard(False)}), ResultReceipt(result_ref=uuid4(), count=99)
    )
    assert replay.receipt == committed.receipt
    assert await store.result(subject, receipt.result_ref) == original_result
    assert (await store.get(subject, initial.intent.session_id)).intent.version == 2
    assert original_result.intent.version == 1
    assert await usage(pg, subject) == (2, 0)
    for other in (QuotaSubject(kind="guest", id=uuid4()), QuotaSubject(kind="auth", id=subject.id)):
        with pytest.raises(SessionError, match="RESULT_NOT_FOUND"):
            await store.result(other, receipt.result_ref)


@pytest.mark.parametrize("failure", [FailureCode.ASR_FAILURE, FailureCode.LLM_FAILURE, FailureCode.BACKEND_FAILURE])
async def test_provider_failure_preserves_session_and_expiry(store, pg, failure):
    subject = QuotaSubject(kind="guest", id=uuid4())
    initial = await store.create(subject)
    op = await prepare(store, subject, initial)
    await store.ledger.release(subject, op, 1, failure)
    assert await store.get(subject, initial.intent.session_id) == initial
    assert await usage(pg, subject) == (0, 0)


async def test_unsupported_catalog_and_patch_binding_release_without_mutation(store, pg):
    subject = QuotaSubject(kind="auth", id=uuid4())
    initial = await store.create(subject)
    for changes in (
        {"amenities": hard(["invented"])},
        {
            "accommodation": hard(
                {
                    "kind": "catalog_other",
                    "catalog_code": "invented",
                }
            )
        },
    ):
        _, _, result = await complete(store, subject, initial, changes)
        assert result.failure_code == "SESSION_STATE_INVALID"
    op = await prepare(store, subject, initial)
    wrong = patch(initial, {"balcony": hard(True)}).model_copy(update={"session_id": uuid4()})
    result = await store.finalize_patch(subject, op, 1, wrong, ResultReceipt(result_ref=uuid4(), count=0))
    assert result.failure_code == "SESSION_STATE_INVALID"
    assert await store.get(subject, initial.intent.session_id) == initial
    assert await usage(pg, subject) == (0, 0)


async def test_expired_session_never_silently_becomes_empty_new_search(store, pg):
    subject = QuotaSubject(kind="guest", id=uuid4())
    initial = await store.create(subject)
    async with pg[1].begin() as conn:
        await conn.execute(
            update(AISearchSession).values(expires_at=func.clock_timestamp() - text("interval '1 second'"))
        )
    with pytest.raises(SessionError, match="SESSION_EXPIRED"):
        await store.get(subject, initial.intent.session_id)
    _, _, failed = await complete(store, subject, initial, {"balcony": hard(True)})
    assert failed.failure_code == "SESSION_EXPIRED"
    assert await usage(pg, subject) == (0, 0)
    async with pg[1]() as conn:
        assert await conn.scalar(select(func.count()).select_from(AISearchSession)) == 1
    reset = await store.reset(subject, initial.intent.session_id, 0)
    assert reset.intent.session_id != initial.intent.session_id and reset.intent.version == 0


async def test_explicit_reset_invalidates_inflight_old_operation(store, pg):
    subject = QuotaSubject(kind="guest", id=uuid4())
    initial = await store.create(subject)
    op = await prepare(store, subject, initial)
    reset = await store.reset(subject, initial.intent.session_id, 0)
    result = await store.finalize_patch(
        subject, op, 1, patch(initial, {"balcony": hard(True)}), ResultReceipt(result_ref=uuid4(), count=0)
    )
    assert result.failure_code == "SESSION_EXPIRED"
    assert await store.get(subject, reset.intent.session_id) == reset
    assert await usage(pg, subject) == (0, 0)
    with pytest.raises(SessionError, match="SESSION_VERSION_CONFLICT"):
        await store.reset(subject, initial.intent.session_id, 0)


async def test_reset_does_not_reset_business_quota(store, pg):
    subject = QuotaSubject(kind="guest", id=uuid4())
    initial = await store.create(subject)
    await complete(store, subject, initial, {"balcony": hard(True)})
    current = await store.get(subject, initial.intent.session_id)
    assert current.expires_at > initial.expires_at
    for _ in range(2):
        current = await store.reset(subject, current.intent.session_id, current.intent.version)
        await complete(store, subject, current, {"terrace": hard(True)})
        current = await store.get(subject, current.intent.session_id)
    fresh = await store.reset(subject, current.intent.session_id, current.intent.version)
    with pytest.raises(QuotaError, match="QUOTA_EXHAUSTED"):
        await store.ledger.reserve(subject, operation(fresh))
    assert await usage(pg, subject) == (3, 0)


async def test_reset_closes_old_identity_even_at_version_limit(store, pg):
    subject = QuotaSubject(kind="guest", id=uuid4())
    initial = await store.create(subject)
    async with pg[1].begin() as conn:
        await conn.execute(update(AISearchSession).values(version=2_147_483_647))
    fresh = await store.reset(subject, initial.intent.session_id, 2_147_483_647)
    # A closed identity cannot be revived by a future expiry/clock adjustment.
    async with pg[1].begin() as conn:
        await conn.execute(
            update(AISearchSession)
            .where(AISearchSession.id == initial.intent.session_id)
            .values(expires_at=func.clock_timestamp() + text("interval '1 day'"))
        )
    with pytest.raises(SessionError, match="SESSION_EXPIRED"):
        await store.get(subject, initial.intent.session_id)
    with pytest.raises(SessionError, match="SESSION_VERSION_CONFLICT"):
        await store.reset(subject, initial.intent.session_id, 2_147_483_647)
    assert fresh.intent.version == 0 and fresh.intent.session_id != initial.intent.session_id


@pytest.mark.parametrize(
    "corrupt",
    [{"schema_version": "ai-search.v2"}, {"taxonomy_version": "future.v2"}, {"criteria": {"sql": "untrusted"}}],
)
async def test_unknown_stored_state_is_not_downgraded_to_empty(store, pg, corrupt):
    subject = QuotaSubject(kind="guest", id=uuid4())
    initial = await store.create(subject)
    async with pg[1].begin() as conn:
        await conn.execute(update(AISearchSession).values(**corrupt))
    with pytest.raises(SessionError, match="SESSION_STATE_INVALID"):
        await store.get(subject, initial.intent.session_id)
    _, _, result = await complete(store, subject, initial, {"balcony": hard(True)})
    assert result.failure_code == "SESSION_STATE_INVALID"
    assert await usage(pg, subject) == (0, 0)


async def test_result_hash_and_expired_replay_fail_closed(store, pg):
    subject = QuotaSubject(kind="guest", id=uuid4())
    initial = await store.create(subject)
    _, receipt, _ = await complete(store, subject, initial, {"balcony": hard(True)})
    async with pg[1].begin() as conn:
        await conn.execute(update(AISearchResult).values(intent_hash="0" * 64))
    with pytest.raises(SessionError, match="RESULT_STATE_INVALID"):
        await store.result(subject, receipt.result_ref)
    async with pg[1].begin() as conn:
        await conn.execute(
            update(AISearchSession).values(expires_at=func.clock_timestamp() - text("interval '1 second'"))
        )
    with pytest.raises(SessionError, match="RESULT_EXPIRED_REQUERY_REQUIRED"):
        await store.result(subject, receipt.result_ref)
    assert await usage(pg, subject) == (1, 0)


async def test_result_write_failure_cannot_commit_session_without_debit(store, pg):
    subject = QuotaSubject(kind="guest", id=uuid4())
    initial = await store.create(subject)
    _, receipt, _ = await complete(store, subject, initial, {"balcony": hard(True)})
    current = await store.get(subject, initial.intent.session_id)
    op = await prepare(store, subject, current)
    with pytest.raises(IntegrityError):
        await store.finalize_patch(subject, op, 1, patch(current, {"terrace": hard(True)}), receipt)
    assert await store.get(subject, current.intent.session_id) == current
    assert await usage(pg, subject) == (1, 1)
    await store.ledger.release(subject, op, 1, FailureCode.BACKEND_FAILURE)
    assert await usage(pg, subject) == (1, 0)


async def test_lease_expires_after_real_session_cas_even_if_caller_catches_error(store, pg):
    ledger = QuotaLedger(pg[1], LeasePolicy(reservation_seconds=60, running_seconds=1, recovery_grace_seconds=0))
    store = SearchSessions(ledger, store.policy, store.vocabulary)
    subject = QuotaSubject(kind="guest", id=uuid4())
    initial = await store.create(subject)
    op = await prepare(store, subject, initial)
    receipt = ResultReceipt(result_ref=uuid4(), count=0)
    callback = store.commit_patch(subject, op, patch(initial, {"balcony": hard(True)}), receipt)

    async def slow(conn, sid, version):
        await callback(conn, sid, version)
        await conn.execute(text("SELECT pg_sleep(1.1)"))

    async with pg[1].begin() as conn:
        with pytest.raises(QuotaError, match="STALE_WORKER"):
            await ledger.finalize_in_transaction(conn, subject, op, 1, receipt, commit_session=slow)
    assert await store.get(subject, initial.intent.session_id) == initial
    async with pg[1]() as conn:
        assert await conn.scalar(select(func.count()).select_from(AISearchResult)) == 0
    await ledger.recover(subject, op.idempotency_key)
    assert await usage(pg, subject) == (0, 0)


async def test_expiry_is_checked_after_waiting_for_session_row_lock(store, pg):
    subject = QuotaSubject(kind="guest", id=uuid4())
    initial = await store.create(subject)
    op = await prepare(store, subject, initial)
    async with pg[1].begin() as blocker:
        await blocker.execute(select(AISearchSession).with_for_update())
        task = asyncio.create_task(
            store.finalize_patch(
                subject, op, 1, patch(initial, {"balcony": hard(True)}), ResultReceipt(result_ref=uuid4(), count=0)
            )
        )
        await asyncio.sleep(0.05)
        await blocker.execute(
            update(AISearchSession).values(expires_at=func.clock_timestamp() - text("interval '1 second'"))
        )
    result = await task
    assert result.failure_code == "SESSION_EXPIRED"
    assert await usage(pg, subject) == (0, 0)
