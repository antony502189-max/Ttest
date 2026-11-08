"""Durable pre-I/O accounting/fencing in owned synthetic schemas, mock HTTP only."""
import asyncio
from dataclasses import replace

import httpx
import pytest
from sqlalchemy import func, insert, select, text, update
from test_fact_refresh import BUNDLE, POLICY, run, state
from test_fact_refresh import coordinator as coordinator_fixture
from test_fact_refresh import proofs as proof_fixture
from test_fact_refresh import refresh_setup as refresh_fixture
from test_fact_supervision import supervisor as make_supervisor
from test_offline_fact_worker import queue

from app.models import ExternalListingSource
from lab.ai_fact_refresh import (
    OPERATIONS,
    REQUEST_BUDGETS,
    REQUEST_CLAIMS,
    SyntheticDetailRefresh,
    SyntheticRefreshUnavailable,
)

pytestmark = pytest.mark.integration
refresh_setup = refresh_fixture
coordinator, proofs = coordinator_fixture, proof_fixture


async def spent(runner):
    async with runner.sessions() as session:
        return (await session.execute(select(REQUEST_BUDGETS.c.used).where(
            REQUEST_BUDGETS.c.namespace == runner._namespace()))).scalar_one()


async def expire(runner):
    async with runner.sessions() as session, session.begin():
        await session.execute(update(REQUEST_CLAIMS).values(lease_until=func.clock_timestamp()))


async def test_other_receipt_cannot_claim_the_same_live_source(refresh_setup):
    runner, source, _, calls, _, _ = refresh_setup
    namespace = runner._namespace()
    token, result = await runner._claim("a" * 64, namespace, source)
    assert token is not None and result == "claimed"
    assert await runner._claim("b" * 64, namespace, source) == (None, "in_progress")
    assert await spent(runner) == 1 and calls == []
    await expire(runner)
    next_token, result = await runner._claim("b" * 64, namespace, source)
    assert next_token is not None and next_token != token and result == "claimed"
    target = await runner._target(source)
    assert (await runner._fetch(target, "a" * 64, namespace, token))[1] == "lease_lost"
    assert calls == [] and await spent(runner) == 2


async def test_two_sources_and_callers_share_one_durable_request_cap(pipeline, coordinator, tmp_path):
    await queue(pipeline)
    await queue(pipeline)
    supervisor = await make_supervisor(tmp_path, coordinator)
    await supervisor.run_once()
    async with pipeline[1]() as session:
        cohort = tuple((a, b) for a, b in (await session.execute(select(
            ExternalListingSource.id, ExternalListingSource.canonical_listing_id))).all())
    calls = []
    def blocked(request):
        calls.append(request)
        return httpx.Response(403)
    runner = SyntheticDetailRefresh(supervisor, policy=replace(POLICY, max_total_requests=1), cohort=cohort,
        transport=httpx.MockTransport(blocked), mock_bundle_sha256=BUNDLE)
    await runner.initialize()
    results = await asyncio.gather(run(runner), run(runner))
    assert "request_capacity" in [value for result in results for value in result.outcomes]
    assert len(calls) == await spent(runner) == 1
    assert supervisor.journal.pending().refresh == 2


@pytest.mark.parametrize("refresh_setup", [replace(POLICY, max_total_requests=1)], indirect=True)
async def test_failed_get_spends_durable_budget_and_reopen_does_not_reset_it(refresh_setup):
    runner, source, listing, calls, _, handler = refresh_setup
    def blocked(request):
        handler(request)
        return httpx.Response(403)
    runner.transport = httpx.MockTransport(blocked)
    assert (await run(runner)).outcomes == ("failed",)
    restarted = SyntheticDetailRefresh(runner.supervisor, policy=runner.policy, cohort=((source, listing),),
        transport=httpx.MockTransport(blocked), mock_bundle_sha256=BUNDLE)
    await restarted.initialize()
    assert (await run(restarted)).outcomes == ("request_capacity",)
    assert len(calls) == await spent(restarted) == 1
    assert runner.supervisor.journal.pending().refresh == 1


async def test_unknown_claim_ack_is_charged_before_dispatch_and_recovers_after_lease(refresh_setup, monkeypatch):
    runner, _, _, calls, _, _ = refresh_setup
    claim = runner._claim
    async def lost_ack(*args):
        await claim(*args)
        raise RuntimeError("PRIVATE_CLAIM_ACK")
    monkeypatch.setattr(runner, "_claim", lost_ack)
    with pytest.raises(SyntheticRefreshUnavailable, match="^SYNTHETIC_DETAIL_REFRESH_UNAVAILABLE$"):
        await run(runner)
    assert calls == [] and await spent(runner) == 1
    monkeypatch.setattr(runner, "_claim", claim)
    assert (await run(runner)).outcomes == ("in_progress",)
    await expire(runner)
    assert (await run(runner)).outcomes == ("refreshed",)
    assert len(calls) == 1 and await spent(runner) == 2


async def test_expired_claim_cannot_dispatch_a_get(refresh_setup, pipeline, monkeypatch):
    runner, _, _, calls, _, _ = refresh_setup
    fetch = runner._fetch
    async def pause_before_dispatch(*args):
        await expire(runner)
        return await fetch(*args)
    before = await state(pipeline)
    monkeypatch.setattr(runner, "_fetch", pause_before_dispatch)
    assert (await run(runner)).outcomes == ("lease_lost",)
    assert await state(pipeline) == before and calls == [] and await spent(runner) == 1


async def test_one_reservation_cannot_dispatch_twice(refresh_setup):
    runner, source, _, calls, _, _ = refresh_setup
    namespace, operation = runner._namespace(), "a" * 64
    token, _ = await runner._claim(operation, namespace, source)
    assert token is not None
    target = await runner._target(source)
    assert (await runner._fetch(target, operation, namespace, token))[1] == "active"
    assert (await runner._fetch(target, operation, namespace, token))[1] == "lease_lost"
    assert len(calls) == await spent(runner) == 1


@pytest.mark.parametrize("refresh_setup", [replace(POLICY, timeout_seconds=5, request_lease_seconds=6)], indirect=True)
async def test_new_owner_fences_a_late_old_http_response(refresh_setup, pipeline):
    runner, _, _, calls, body, _ = refresh_setup
    entered = [asyncio.Event(), asyncio.Event()]
    release = [asyncio.Event(), asyncio.Event()]
    async def response(request):
        index = len(calls)
        calls.append(request)
        entered[index].set()
        await release[index].wait()
        return httpx.Response(200, json={**body, "raw": {"owner": index}})
    runner.transport = httpx.MockTransport(response)
    before = await state(pipeline)
    first = asyncio.create_task(run(runner))
    second = None
    try:
        await asyncio.wait_for(entered[0].wait(), 2)
        await expire(runner)
        second = asyncio.create_task(run(runner))
        await asyncio.wait_for(entered[1].wait(), 2)
        release[0].set()
        assert (await first).outcomes == ("lease_lost",)
        assert await state(pipeline) == before
        release[1].set()
        assert (await second).outcomes == ("refreshed",)
        assert (await state(pipeline))[0].raw_payload == {"owner": 1}
        assert await spent(runner) == 2
    finally:
        for event in release:
            event.set()
        await asyncio.gather(first, *([second] if second else []), return_exceptions=True)


async def test_final_fence_failure_rolls_back_source_projection_and_receipt(refresh_setup, pipeline, monkeypatch):
    runner, _, _, _, _, _ = refresh_setup
    publish = pipeline[0]._publish
    async def expire_in_transaction(session, *args):
        await publish(session, *args)
        await session.execute(update(REQUEST_CLAIMS).values(lease_until=func.clock_timestamp()))
    before = await state(pipeline)
    monkeypatch.setattr(pipeline[0], "_publish", expire_in_transaction)
    assert (await run(runner)).outcomes == ("lease_lost",)
    assert await state(pipeline) == before and await spent(runner) == 1


async def test_claim_waiter_rechecks_effect_committed_while_waiting(refresh_setup, monkeypatch):
    runner, source, _, calls, _, _ = refresh_setup
    finish = runner._finish_request
    entered, release = asyncio.Event(), asyncio.Event()
    async def hold_commit(*args):
        await finish(*args)
        entered.set()
        await release.wait()
    monkeypatch.setattr(runner, "_finish_request", hold_commit)
    first = asyncio.create_task(run(runner))
    second = None
    try:
        await asyncio.wait_for(entered.wait(), 2)
        async with runner.sessions() as session:
            operation = (await session.execute(select(REQUEST_CLAIMS.c.operation))).scalar_one()
        second = asyncio.create_task(runner._claim(operation, runner._namespace(), source))
        for _ in range(100):
            async with runner.sessions() as session:
                waiting = await session.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE wait_event_type='Lock' "
                    "AND position('synthetic_ai_detail_request_claims' in query)>0"))
            if waiting:
                break
            await asyncio.sleep(.01)
        assert waiting
        release.set()
        assert (await first).outcomes == ("refreshed",)
        assert await second == (None, "already_applied")
        assert len(calls) == await spent(runner) == 1
    finally:
        release.set()
        await asyncio.gather(first, *([second] if second else []), return_exceptions=True)


@pytest.mark.parametrize("outcome", ["stale", "capacity"])
@pytest.mark.parametrize("waiter", [False, True])
@pytest.mark.parametrize("refresh_setup", [replace(POLICY, max_operations=1, max_total_requests=2)], indirect=True)
async def test_terminal_write_finishes_claim_and_unblocks_retry_without_refund(
        refresh_setup, pipeline, monkeypatch, outcome, waiter):
    runner, source, _, calls, _, _ = refresh_setup
    operation, namespace = "a" * 64, runner._namespace()
    token, result = await runner._claim(operation, namespace, source)
    assert result == "claimed"
    target = await runner._target(source)
    detail, health = await runner._fetch(target, operation, namespace, token)
    async with runner.sessions() as session, session.begin():
        if outcome == "stale":
            await session.execute(update(ExternalListingSource).where(ExternalListingSource.id == source)
                                  .values(raw_payload={"concurrent_change": True}))
        else:
            await session.execute(insert(OPERATIONS).values(operation="f" * 64, namespace=namespace,
                source_id=source, committed_at=func.clock_timestamp()))
    before = await state(pipeline)
    entered, release = asyncio.Event(), asyncio.Event()
    finish = runner._finish_request

    async def pause_commit(*args):
        await finish(*args)
        entered.set()
        await release.wait()

    if waiter:
        monkeypatch.setattr(runner, "_finish_request", pause_commit)
    write = asyncio.create_task(runner._write(target, operation, namespace, detail, health, token))
    retry = None
    try:
        if waiter:
            await asyncio.wait_for(entered.wait(), 2)
            retry = asyncio.create_task(runner._claim(operation, namespace, source))
            for _ in range(100):
                async with runner.sessions() as session:
                    waiting = await session.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE wait_event_type='Lock' "
                        "AND position('synthetic_ai_detail_request_claims' in query)>0"))
                if waiting:
                    break
                await asyncio.sleep(.01)
            assert waiting
            release.set()
        assert await write == outcome
        assert await state(pipeline) == before  # no new source/projection/success receipt
        if not waiter:
            async with runner.sessions() as session:
                assert await session.scalar(select(REQUEST_CLAIMS.c.status)) == "finished"
            retry = asyncio.create_task(runner._claim(operation, namespace, source))
        next_token, status = await retry
        assert status == "claimed" and next_token != token
        assert len(calls) == 1 and await spent(runner) == 2
        monkeypatch.setattr(runner, "_finish_request", finish)
        target = await runner._target(source)
        detail, health = await runner._fetch(target, operation, namespace, next_token)
        assert await runner._write(target, operation, namespace, detail, health, next_token) == (
            "refreshed" if outcome == "stale" else "capacity")
        assert len(calls) == await spent(runner) == 2
        assert await runner._claim("b" * 64, namespace, source) == (None, "request_capacity")
    finally:
        release.set()
        await asyncio.gather(write, *([retry] if retry else []), return_exceptions=True)
