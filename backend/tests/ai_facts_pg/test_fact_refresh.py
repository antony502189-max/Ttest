"""Mock-only detail receipt -> guarded source -> actual fact/proof recovery."""

import asyncio
import hashlib
import json
import time
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select, text, update
from test_fact_coordinator import coordinator as coordinator_fixture
from test_fact_supervision import supervisor as make_supervisor
from test_offline_fact_worker import CASES, queue
from test_query_proofs import guard
from test_query_proofs import proofs as proof_fixture

from app.models import ExternalListingSource
from app.models.ai_fact_pipeline import AiFactRematchEvent
from app.repositories.ai_fact_quality import source_check_health_predicate
from app.services.ai_fact_coordinator import FactCoordinatorCursor
from lab.ai_fact_refresh import (
    OPERATIONS,
    REQUEST_CLAIMS,
    SyntheticDetailRefresh,
    SyntheticRefreshPolicy,
    SyntheticRefreshUnavailable,
)

pytestmark = pytest.mark.integration
coordinator, proofs = coordinator_fixture, proof_fixture
BUNDLE = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
POLICY = SyntheticRefreshPolicy("synthetic", "example.invalid", 10, 131_072, 1, 10, 20, 30)


@pytest_asyncio.fixture
async def refresh_setup(pipeline, coordinator, tmp_path, request):
    await queue(pipeline)
    supervisor = await make_supervisor(tmp_path, coordinator)
    assert await supervisor.run_once() == "committed"
    async with pipeline[1]() as session:
        source_id, listing_id = (await session.execute(select(
            ExternalListingSource.id, ExternalListingSource.canonical_listing_id))).one()
    calls = []
    document = {"schema_version": "synthetic-detail.v1", "source_id": str(source_id),
        "canonical_listing_id": str(listing_id), "source_name": "synthetic", "raw": {"synthetic": "new detail"},
        "normalized": {"packet": next(c["packet"] for c in CASES["cases"] if c["name"] == "pets_allow")}, "price": None}

    def handler(request):
        assert request.url.host == "example.invalid"
        assert pipeline[1].kw["bind"].pool.checkedout() == 0  # no capture/source transaction spans mock I/O
        calls.append(request)
        return httpx.Response(200, json=document)

    runner = SyntheticDetailRefresh(supervisor, policy=getattr(request, "param", POLICY), cohort=((source_id, listing_id),),
                                    transport=httpx.MockTransport(handler), mock_bundle_sha256=BUNDLE)
    await runner.initialize()
    return runner, source_id, listing_id, calls, document, handler


async def run(runner, revision=1, expected=None):
    return await runner.run_receipt(revision, expected_digest=expected or runner.supervisor.journal.receipt_digest(revision))


async def state(pipeline):
    async with pipeline[1]() as session:
        row = (await session.execute(select(ExternalListingSource.raw_payload,
            ExternalListingSource.normalized_payload, ExternalListingSource.last_success_at,
            ExternalListingSource.content_updated_at, ExternalListingSource.last_state_check_result,
            ExternalListingSource.current_status,
            source_check_health_predicate(ExternalListingSource.__table__, func.statement_timestamp()).label("healthy")))).one()
        return row, await session.scalar(select(func.count()).select_from(OPERATIONS)), await session.scalar(
            select(func.count()).select_from(AiFactRematchEvent))


async def test_detail_refresh_recovers_current_facts_without_implicit_ack(pipeline, refresh_setup):
    runner, source, listing, calls, document, _ = refresh_setup
    store, coordinator = runner.supervisor.journal, runner.supervisor.coordinator
    assert await guard(coordinator.proofs, listing)
    assert (await state(pipeline))[0].last_success_at is None
    result = await run(runner)
    assert result.outcomes == ("refreshed",) and not result.acknowledged and len(calls) == 1
    row, receipts, _events = await state(pipeline)
    assert row.last_success_at is not None and row.raw_payload == document["raw"] and row.healthy
    assert receipts == 1 and store.pending().refresh == 1
    assert not await guard(coordinator.proofs, listing)  # old projection/proof excluded until actual extraction
    tick = await coordinator.run_once(FactCoordinatorCursor())
    assert tick.proofs_prepared == 1 and "succeeded" in tick.job_outcomes and not tick.content_refresh_due
    assert await guard(coordinator.proofs, listing)
    after = await state(pipeline)
    assert (await run(runner)).outcomes == ("already_applied",) and len(calls) == 1
    assert await state(pipeline) == after
    assert store.pending().refresh == 1
    store.acknowledge(1, expected_digest=store.receipt_digest(1))  # explicit caller decision after proof recovery
    assert store.pending().refresh == 0 and store.receipt(1)["content_refresh_due"] == [str(source)]


async def test_unknown_commit_outcome_reopens_without_second_get_or_publication(pipeline, refresh_setup, monkeypatch):
    runner, source, listing, calls, _, handler = refresh_setup
    write = runner._write

    async def lose_ack(*args):
        await write(*args)
        raise RuntimeError("PRIVATE_UNKNOWN_COMMIT")

    monkeypatch.setattr(runner, "_write", lose_ack)
    with pytest.raises(SyntheticRefreshUnavailable, match="^SYNTHETIC_DETAIL_REFRESH_UNAVAILABLE$") as error:
        await run(runner)
    assert error.value.__cause__ is None
    after = await state(pipeline)
    restarted = SyntheticDetailRefresh(runner.supervisor, policy=POLICY, cohort=((source, listing),),
        transport=httpx.MockTransport(handler), mock_bundle_sha256=BUNDLE)
    await restarted.initialize()
    assert (await run(restarted)).outcomes == ("already_applied",)
    assert await state(pipeline) == after and len(calls) == 1


@pytest.mark.parametrize("status", [403, 429, 302, 404, 500])
async def test_http_failure_does_not_refresh_or_retire_manual_source(pipeline, refresh_setup, status):
    runner, _, _, calls, _, handler = refresh_setup
    async with pipeline[1]() as session, session.begin():
        await session.execute(text("UPDATE external_listing_sources SET last_success_at=clock_timestamp()-interval '61 seconds'"))
    before = await state(pipeline)

    def fail(request):
        handler(request)
        return httpx.Response(status, headers={"location": "https://real.example/listing"})

    runner.transport = httpx.MockTransport(fail)
    assert (await run(runner)).outcomes == ("failed",)
    after = await state(pipeline)
    assert after[0].last_success_at == before[0].last_success_at and after[0].raw_payload == before[0].raw_payload
    assert after[0].current_status == "active" and not after[0].healthy
    assert after[1] == 0 and len(calls) == 1 and runner.supervisor.journal.pending().refresh == 1


@pytest.mark.parametrize("fault", ["identity", "canonical", "source", "packet", "size", "json", "content_type", "encoding"])
async def test_invalid_details_are_not_promoted_to_fresh_content(pipeline, refresh_setup, fault):
    runner, _, _, calls, document, handler = refresh_setup

    def invalid(request):
        handler(request)
        if fault == "size":
            return httpx.Response(200, content=b"x" * 131_073, headers={"content-type": "application/json"})
        if fault == "json":
            return httpx.Response(200, content=b"not json", headers={"content-type": "application/json"})
        body = dict(document)
        body.update({"identity": {"source_id": str(uuid4())}, "canonical": {"canonical_listing_id": str(uuid4())},
            "source": {"source_name": "other"}, "packet": {"normalized": {"packet": {}}}}.get(fault, {}))
        return httpx.Response(200, json=body, headers={"content-type": "text/html"} if fault == "content_type" else
            {"content-encoding": "gzip"} if fault == "encoding" else {})

    runner.transport = httpx.MockTransport(invalid)
    before = await state(pipeline)
    assert (await run(runner)).outcomes == ("failed",)
    after = await state(pipeline)
    assert after[0].last_success_at == before[0].last_success_at and after[0].normalized_payload == before[0].normalized_payload
    assert after[1] == 0 and len(calls) == 1 and not after[0].healthy


@pytest.mark.parametrize("change", ["payload", "fingerprint", "url", "source", "canonical", "retired", "deleted", "hidden", "health"])
async def test_racing_catalog_change_is_not_overwritten(pipeline, refresh_setup, change):
    runner, _, _, calls, _, handler = refresh_setup

    async def race(request):
        response = handler(request)
        sql = {"payload": "UPDATE external_listing_sources SET raw_payload=jsonb_build_object('race',true)",
            "fingerprint": "UPDATE external_listing_sources SET fingerprint=repeat('a',64)",
            "url": "UPDATE external_listing_sources SET source_url='https://example.invalid/other'",
            "source": "UPDATE external_listing_sources SET source_name='other'",
            "canonical": "UPDATE external_listing_sources SET canonical_listing_id='00000000-0000-0000-0000-000000000001'",
            "retired": "UPDATE external_listing_sources SET current_status='missing'",
            "deleted": "DELETE FROM external_listing_sources",
            "hidden": "UPDATE listings SET status='hidden'",
            "health": "UPDATE external_listing_sources SET last_checked_at=clock_timestamp(),last_state_check_result='blocked'"}[change]
        async with pipeline[1]() as session, session.begin():
            await session.execute(text(sql))
        return response

    runner.transport = httpx.MockTransport(race)
    assert (await run(runner)).outcomes == ("stale",) and len(calls) == 1
    async with pipeline[1]() as session:
        assert await session.scalar(select(func.count()).select_from(OPERATIONS)) == 0
        assert await session.scalar(select(func.count()).select_from(ExternalListingSource).where(
            ExternalListingSource.last_success_at.is_not(None))) == 0
    assert runner.supervisor.journal.pending().refresh == 1


async def test_receipt_insert_failure_rolls_back_source_and_projection(pipeline, refresh_setup):
    runner, _, _, calls, _, _ = refresh_setup
    async with pipeline[1]() as session, session.begin():
        await session.execute(text("CREATE FUNCTION fail_refresh_receipt() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN RAISE EXCEPTION 'PRIVATE_SYNTHETIC_COMMIT_FAULT'; END $$"))
        await session.execute(text("CREATE TRIGGER fail_receipt BEFORE INSERT ON synthetic_ai_detail_refresh_receipts "
            "FOR EACH ROW EXECUTE FUNCTION fail_refresh_receipt()"))
    before = await state(pipeline)
    with pytest.raises(SyntheticRefreshUnavailable) as error:
        await run(runner)
    assert error.value.__cause__ is None and "PRIVATE" not in str(error.value)
    assert await state(pipeline) == before
    async with pipeline[1]() as session, session.begin():
        await session.execute(text("DROP TRIGGER fail_receipt ON synthetic_ai_detail_refresh_receipts"))
        await session.execute(update(REQUEST_CLAIMS).values(lease_until=func.clock_timestamp()))
    assert (await run(runner)).outcomes == ("refreshed",) and len(calls) == 2
    assert (await state(pipeline))[1] == 1


@pytest.mark.parametrize("cancel", [False, True])
async def test_mock_timeout_or_cancel_never_marks_content_fresh(pipeline, refresh_setup, cancel):
    runner, _, _, calls, _, handler = refresh_setup
    entered = asyncio.Event()

    async def blocked(request):
        handler(request)
        entered.set()
        await asyncio.sleep(10)
        raise AssertionError("must be cancelled")

    runner.transport = httpx.MockTransport(blocked)
    before = await state(pipeline)
    if cancel:
        task = asyncio.create_task(run(runner))
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert await state(pipeline) == before
    else:
        assert (await run(runner)).outcomes == ("failed",)
        assert (await state(pipeline))[0].last_success_at is None
    assert len(calls) == 1 and (await state(pipeline))[1] == 0


async def test_fresh_source_skips_http_without_renewing_age(pipeline, refresh_setup):
    runner, _, _, calls, _, _ = refresh_setup
    async with pipeline[1]() as session, session.begin():
        await session.execute(text("UPDATE external_listing_sources SET last_success_at=clock_timestamp()"))
    before = await state(pipeline)
    assert (await run(runner)).outcomes == ("already_fresh",) and calls == []
    assert await state(pipeline) == before


@pytest.mark.parametrize("mutation", ["digest", "cohort", "transport", "url", "bundle", "policy"])
async def test_scope_and_binding_fail_closed_before_get(pipeline, refresh_setup, mutation):
    runner, _, _, calls, _, _ = refresh_setup
    if mutation == "cohort":
        runner.cohort = {uuid4(): uuid4()}
    elif mutation == "transport":
        runner.transport = httpx.AsyncHTTPTransport()
    elif mutation == "bundle":
        runner.mock_bundle_sha256 = "f" * 64
    elif mutation == "policy":
        runner.policy = replace(POLICY, max_requests=1)
    elif mutation == "url":
        async with pipeline[1]() as session, session.begin():
            await session.execute(text("UPDATE external_listing_sources SET source_url='https://real.example/listing'"))
    with pytest.raises(SyntheticRefreshUnavailable):
        await run(runner, expected="f" * 64 if mutation == "digest" else None)
    assert calls == [] and (await state(pipeline))[1] == 0
    if mutation == "transport":
        await runner.transport.aclose()


async def test_request_bound_rejects_whole_receipt_before_partial_work(pipeline, coordinator, tmp_path):
    await queue(pipeline)
    await queue(pipeline)
    supervisor = await make_supervisor(tmp_path, coordinator)
    assert await supervisor.run_once() == "committed"
    async with pipeline[1]() as session:
        cohort = tuple((a, b) for a, b in (await session.execute(select(
            ExternalListingSource.id, ExternalListingSource.canonical_listing_id))).all())
    calls = []
    runner = SyntheticDetailRefresh(supervisor, policy=replace(POLICY, max_requests=1), cohort=cohort,
        transport=httpx.MockTransport(lambda request: calls.append(request)), mock_bundle_sha256=BUNDLE)
    await runner.initialize()
    with pytest.raises(SyntheticRefreshUnavailable):
        await run(runner)
    assert not calls and (await state_for_count(pipeline)) == 0


async def state_for_count(pipeline):
    async with pipeline[1]() as session:
        return await session.scalar(select(func.count()).select_from(OPERATIONS))


async def test_operation_capacity_stops_new_receipt_without_pruning(pipeline, coordinator, tmp_path):
    # Independent journal because immutable consumer policy includes retention cap.
    await queue(pipeline)
    supervisor = await make_supervisor(tmp_path, coordinator)
    await supervisor.run_once()
    async with pipeline[1]() as session:
        source, listing = (await session.execute(select(
            ExternalListingSource.id, ExternalListingSource.canonical_listing_id))).one()
    packet = next(c["packet"] for c in CASES["cases"] if c["name"] == "pets_allow")
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"schema_version": "synthetic-detail.v1", "source_id": str(source),
            "canonical_listing_id": str(listing), "source_name": "synthetic", "raw": {"synthetic": True},
            "normalized": {"packet": packet}, "price": None})

    runner = SyntheticDetailRefresh(supervisor, policy=replace(POLICY, max_operations=1), cohort=((source, listing),),
        transport=httpx.MockTransport(handler), mock_bundle_sha256=BUNDLE)
    await runner.initialize()
    assert (await run(runner)).outcomes == ("refreshed",)
    async with pipeline[1]() as session, session.begin():
        await session.execute(text("UPDATE external_listing_sources SET last_success_at=clock_timestamp()-interval '61 seconds'"))
    supervisor.clock = lambda: 9_000_000_000.0  # synthetic journal clock only; permit the next explicit tick
    assert await supervisor.run_once() == "committed"
    assert supervisor.journal.receipt(2)["content_refresh_due"] == [str(source)]
    assert (await run(runner, revision=2)).outcomes == ("capacity",) and len(calls) == 1
    assert await state_for_count(pipeline) == 1 and supervisor.journal.pending().refresh == 2


async def test_stored_jsonb_expansion_cannot_exceed_snapshot_capture_bound(pipeline, refresh_setup):
    runner, _, _, calls, document, handler = refresh_setup
    body = dict(document, raw={"padding": {"x" + str(i): 0 for i in range(12_000)}})
    response = httpx.Response(200, json=body)
    assert len(response.content) < POLICY.max_payload_bytes

    def large(request):
        handler(request)
        return response

    runner.transport = httpx.MockTransport(large)
    before = await state(pipeline)
    assert (await run(runner)).outcomes == ("failed",) and len(calls) == 1
    after = await state(pipeline)
    assert after[0].last_success_at is None and after[0].raw_payload == before[0].raw_payload and after[1] == 0


async def test_concurrent_calls_have_one_pre_http_owner_and_one_durable_write(pipeline, refresh_setup):
    runner, _, _, calls, document, _ = refresh_setup
    entered, release = asyncio.Event(), asyncio.Event()

    async def fetch(request):
        calls.append(request)
        entered.set()
        await release.wait()
        return httpx.Response(200, json=document)

    runner.transport = httpx.MockTransport(fetch)
    first = asyncio.create_task(run(runner))
    await asyncio.wait_for(entered.wait(), 1)
    assert (await run(runner)).outcomes == ("in_progress",)
    release.set()
    assert (await first).outcomes == ("refreshed",)
    assert len(calls) == 1 and (await state(pipeline))[1] == 1
    after = await state(pipeline)
    assert (await run(runner)).outcomes == ("already_applied",) and await state(pipeline) == after


async def test_lock_or_commit_delay_does_not_extend_content_observation_time(pipeline, refresh_setup, monkeypatch):
    runner, _, _, _, _, _ = refresh_setup
    write = runner._write
    observed = []

    async def delayed(target, *args):
        observed.append(target.row.checked_at)
        await asyncio.sleep(0.1)
        return await write(target, *args)

    monkeypatch.setattr(runner, "_write", delayed)
    assert (await run(runner)).outcomes == ("refreshed",)
    row = (await state(pipeline))[0]
    assert row.last_success_at == observed[0] and row.content_updated_at == observed[0]


async def test_unchanged_detail_refreshes_check_age_without_faking_content_change(pipeline, refresh_setup):
    runner, _, _, calls, document, handler = refresh_setup
    before = (await state(pipeline))[0]
    same = dict(document, raw=before.raw_payload, normalized=before.normalized_payload)

    def unchanged(request):
        handler(request)
        return httpx.Response(200, json=same)

    runner.transport = httpx.MockTransport(unchanged)
    assert (await run(runner)).outcomes == ("refreshed",) and len(calls) == 1
    after = (await state(pipeline))[0]
    assert after.last_success_at is not None and after.content_updated_at == before.content_updated_at


@pytest.mark.parametrize("scope", ["consumer", "coordinator"])
async def test_configuration_drift_during_get_cannot_commit(pipeline, refresh_setup, scope):
    runner, _, _, calls, _, handler = refresh_setup

    def drift(request):
        response = handler(request)
        if scope == "consumer":
            runner.policy = replace(POLICY, max_requests=1)
        else:
            coordinator = runner.supervisor.coordinator
            coordinator.sources["synthetic"] = replace(coordinator.sources["synthetic"], content_max_age_seconds=59)
        return response

    runner.transport = httpx.MockTransport(drift)
    before = await state(pipeline)
    with pytest.raises(SyntheticRefreshUnavailable):
        await run(runner)
    assert await state(pipeline) == before and len(calls) == 1


async def test_synchronous_builder_overrun_is_not_committed_as_fresh(pipeline, coordinator, tmp_path):
    base = coordinator.sources["synthetic"]

    def slow(snapshot):
        if json.loads(snapshot.raw_json).get("slow"):
            time.sleep(1.1)  # asyncio timeout cannot preempt this; post-return guard must reject it
        return base.builder(snapshot)

    coordinator.sources["synthetic"] = replace(base, builder=slow)
    coordinator.workers[0].builder = slow
    await queue(pipeline)
    supervisor = await make_supervisor(tmp_path, coordinator)
    await supervisor.run_once()
    async with pipeline[1]() as session:
        source, listing = (await session.execute(select(
            ExternalListingSource.id, ExternalListingSource.canonical_listing_id))).one()
    body = {"schema_version": "synthetic-detail.v1", "source_id": str(source),
        "canonical_listing_id": str(listing), "source_name": "synthetic", "raw": {"slow": True},
        "normalized": {"packet": next(c["packet"] for c in CASES["cases"] if c["name"] == "pets_allow")}, "price": None}
    runner = SyntheticDetailRefresh(supervisor, policy=POLICY, cohort=((source, listing),),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)), mock_bundle_sha256=BUNDLE)
    await runner.initialize()
    assert (await run(runner)).outcomes == ("failed",)
    assert (await state(pipeline))[0].last_success_at is None and await state_for_count(pipeline) == 0


@pytest.mark.parametrize("isolation", ["READ COMMITTED", "REPEATABLE READ"])
async def test_concurrent_distinct_sources_cannot_overrun_global_receipt_cap(
        pipeline, coordinator, tmp_path, monkeypatch, isolation):
    await queue(pipeline)
    await queue(pipeline)
    supervisor = await make_supervisor(tmp_path, coordinator)
    await supervisor.run_once()
    async with pipeline[1]() as session:
        cohort = tuple((a, b) for a, b in (await session.execute(select(
            ExternalListingSource.id, ExternalListingSource.canonical_listing_id))).all())
    runner = SyntheticDetailRefresh(supervisor, policy=replace(POLICY, max_operations=1), cohort=cohort,
        transport=httpx.MockTransport(lambda request: None), mock_bundle_sha256=BUNDLE)
    await runner.initialize()
    targets, documents, tokens = [], [], []
    namespace = runner._namespace()
    for i, (source, listing) in enumerate(cohort):
        body = {"schema_version": "synthetic-detail.v1", "source_id": str(source),
            "canonical_listing_id": str(listing), "source_name": "synthetic", "raw": {"capacity": True},
            "normalized": {"packet": next(c["packet"] for c in CASES["cases"] if c["name"] == "pets_allow")}, "price": None}
        runner.transport = httpx.MockTransport(lambda request, body=body: httpx.Response(200, json=body))
        target = await runner._target(source)
        token, _ = await runner._claim(str(i) * 64, namespace, source)
        assert token is not None
        document, result = await runner._fetch(target, str(i) * 64, namespace, token)
        assert document is not None and result == "active"
        targets.append(target)
        documents.append(document)
        tokens.append(token)
    pipeline[1].kw["bind"].update_execution_options(isolation_level=isolation)
    authority = pipeline[0]._authority
    both = asyncio.Event()
    entered = []

    async def synchronize(session, listing_id, *, lock=True):
        result = await authority(session, listing_id, lock=lock)
        if lock:
            entered.append(listing_id)
            if len(entered) == 2:
                both.set()
            await asyncio.wait_for(both.wait(), 5)
        return result

    monkeypatch.setattr(pipeline[0], "_authority", synchronize)
    results = await asyncio.gather(*(runner._write(target, str(i) * 64, namespace, document, "active", tokens[i])
        for i, (target, document) in enumerate(zip(targets, documents, strict=True))))
    assert sorted(results) == ["capacity", "refreshed"] and await state_for_count(pipeline) == 1
    async with pipeline[1]() as session:
        assert await session.scalar(select(func.count()).select_from(ExternalListingSource).where(
            ExternalListingSource.last_success_at.is_not(None))) == 1


@pytest.mark.parametrize("field,nested,old,new", [
    ("raw", False, True, 1), ("raw", False, False, 0), ("raw", False, 1, True), ("raw", False, 0, False),
    ("raw", True, True, 1), ("normalized", True, False, 0), ("normalized", False, True, 1),
])
async def test_json_type_change_updates_fingerprint_and_content_time(refresh_setup, pipeline, field, nested, old, new):
    runner, source, _, _, document, _ = refresh_setup
    async with pipeline[1]() as session, session.begin():
        row = (await session.execute(select(ExternalListingSource.raw_payload,
            ExternalListingSource.normalized_payload).where(ExternalListingSource.id == source))).one()
        raw, normalized = dict(row.raw_payload), dict(row.normalized_payload)
        payload = raw if field == "raw" else normalized
        payload["flag"] = [{"value": old}] if nested else old
        await session.execute(update(ExternalListingSource).values(raw_payload=raw, normalized_payload=normalized,
            content_updated_at=func.clock_timestamp() - text("interval '1 day'")))
    async with pipeline[1]() as session:
        before = (await session.execute(select(ExternalListingSource.fingerprint,
            ExternalListingSource.content_updated_at).where(ExternalListingSource.id == source))).one()
        old_fingerprint, old_time = before.fingerprint, before.content_updated_at
    body = dict(document, raw=dict(raw), normalized=dict(normalized))
    body[field]["flag"] = [{"value": new}] if nested else new
    runner.transport = httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    assert (await run(runner)).outcomes == ("refreshed",)
    async with pipeline[1]() as session:
        after = (await session.execute(select(ExternalListingSource.fingerprint, ExternalListingSource.content_updated_at,
            ExternalListingSource.raw_payload, ExternalListingSource.normalized_payload).where(
                ExternalListingSource.id == source))).one()
        assert after.fingerprint != old_fingerprint
        assert after.content_updated_at > old_time
        assert type((after.raw_payload if field == "raw" else after.normalized_payload)["flag"]
                    if not nested else (after.raw_payload if field == "raw" else after.normalized_payload)["flag"][0]["value"]) is type(new)


@pytest.mark.parametrize("headers", [
    {"content-type": "Application/JSON; charset=utf-8", "content-encoding": "Identity"},
    {"content-type": " application/json ; charset=utf-8 ", "content-encoding": " identity "},
])
async def test_equivalent_header_case_and_whitespace_are_accepted(refresh_setup, pipeline, headers):
    runner, _, _, _, document, _ = refresh_setup
    runner.transport = httpx.MockTransport(lambda request: httpx.Response(200, json=document, headers=headers))
    assert (await run(runner)).outcomes == ("refreshed",)
    assert (await state(pipeline))[1] == 1


@pytest.mark.parametrize("replacement", ["transport", "handler"])
async def test_declared_mock_label_allows_dynamic_callbacks_but_not_unbound_source_writes(
        refresh_setup, pipeline, replacement):
    runner, _, _, calls, document, _ = refresh_setup
    binding = runner.binding

    def other(request):
        calls.append(request)
        return httpx.Response(200, json=dict(document, source_id=str(uuid4())))

    if replacement == "transport":
        runner.transport = httpx.MockTransport(other)
    else:
        runner.transport.handler = other
    # A caller-supplied bundle label is not callback/response attestation.
    assert runner._configuration() == binding
    before = await state(pipeline)
    assert (await run(runner)).outcomes == ("failed",)
    after = await state(pipeline)
    assert after[0].raw_payload == before[0].raw_payload and after[0].last_success_at == before[0].last_success_at
    assert after[1] == 0 and len(calls) == 1 and runner.supervisor.journal.pending().refresh == 1


@pytest.mark.parametrize("failure", ["http", "invalid", "database"])
async def test_public_multi_source_partial_commit_reopen_and_recovery(
        pipeline, coordinator, tmp_path, failure):
    await queue(pipeline)
    await queue(pipeline)
    async with pipeline[1]() as session, session.begin():
        cohort = tuple((a, b) for a, b in (await session.execute(select(
            ExternalListingSource.id, ExternalListingSource.canonical_listing_id).order_by(ExternalListingSource.id))).all())
        for source, _ in cohort:
            await session.execute(update(ExternalListingSource).where(ExternalListingSource.id == source).values(
                source_url=f"https://example.invalid/{source.hex}"))
    supervisor = await make_supervisor(tmp_path, coordinator)
    assert await supervisor.run_once() == "committed"
    first, second = cohort[0][0], cohort[1][0]
    calls, recovering = [], [False]
    documents = {source.hex: {"schema_version": "synthetic-detail.v1", "source_id": str(source),
        "canonical_listing_id": str(listing), "source_name": "synthetic", "raw": {"new": True},
        "normalized": {"packet": next(c["packet"] for c in CASES["cases"] if c["name"] == "pets_allow")}, "price": None}
        for source, listing in cohort}

    def response(request):
        source = request.url.path.strip("/")
        calls.append(source)
        if source == second.hex and not recovering[0]:
            if failure == "http":
                return httpx.Response(500)
            if failure == "invalid":
                return httpx.Response(200, json={"invalid": True})
        return httpx.Response(200, json=documents[source])

    runner = SyntheticDetailRefresh(supervisor, policy=POLICY, cohort=cohort,
        transport=httpx.MockTransport(response), mock_bundle_sha256=BUNDLE)
    await runner.initialize()
    if failure == "database":
        async with pipeline[1]() as session, session.begin():
            await session.execute(text("CREATE FUNCTION fail_second_refresh() RETURNS trigger LANGUAGE plpgsql AS $$ "
                f"BEGIN IF NEW.source_id='{second}'::uuid THEN RAISE EXCEPTION 'SYNTHETIC_FAULT'; END IF; RETURN NEW; END $$"))
            await session.execute(text("CREATE TRIGGER fail_second BEFORE INSERT ON synthetic_ai_detail_refresh_receipts "
                "FOR EACH ROW EXECUTE FUNCTION fail_second_refresh()"))
        with pytest.raises(SyntheticRefreshUnavailable):
            await run(runner)
    else:
        assert (await run(runner)).outcomes == ("refreshed", "failed")
    assert await state_for_count(pipeline) == 1
    assert not await guard(coordinator.proofs, cohort[0][1])
    async with pipeline[1]() as session:
        saved = (await session.execute(select(ExternalListingSource.last_success_at,
            ExternalListingSource.content_updated_at, ExternalListingSource.fingerprint).where(ExternalListingSource.id == first))).one()
        publications = await session.scalar(select(func.count()).select_from(AiFactRematchEvent).where(
            AiFactRematchEvent.canonical_listing_id == cohort[0][1]))
    if failure == "database":
        async with pipeline[1]() as session, session.begin():
            await session.execute(text("DROP TRIGGER fail_second ON synthetic_ai_detail_refresh_receipts"))
            await session.execute(update(REQUEST_CLAIMS).values(lease_until=func.clock_timestamp()))
    recovering[0] = True
    reopened_supervisor = await make_supervisor(tmp_path, coordinator)
    reopened = SyntheticDetailRefresh(reopened_supervisor, policy=POLICY, cohort=cohort,
        transport=httpx.MockTransport(response), mock_bundle_sha256=BUNDLE)
    await reopened.initialize()
    assert (await run(reopened)).outcomes == ("already_applied", "refreshed")
    assert calls.count(first.hex) == 1 and calls.count(second.hex) == 2
    assert await state_for_count(pipeline) == 2 and supervisor.journal.pending().refresh == 2
    async with pipeline[1]() as session:
        assert (await session.execute(select(ExternalListingSource.last_success_at,
            ExternalListingSource.content_updated_at, ExternalListingSource.fingerprint).where(ExternalListingSource.id == first))).one() == saved
        assert await session.scalar(select(func.count()).select_from(AiFactRematchEvent).where(
            AiFactRematchEvent.canonical_listing_id == cohort[0][1])) == publications
    tick = await coordinator.run_once(FactCoordinatorCursor())
    assert tick.proofs_prepared == 2 and all([await guard(coordinator.proofs, listing) for _, listing in cohort])
    assert supervisor.journal.pending().refresh == 2  # no implicit ACK after full recovery
