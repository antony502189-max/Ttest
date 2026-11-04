"""Finite coordinator/recovery on owned synthetic PG; no provider or importer I/O."""
import asyncio

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from test_offline_fact_worker import VERSION, builder, mapping, queue
from test_query_proofs import guard
from test_query_proofs import proofs as proof_fixture

from app.models.ai_fact_pipeline import AiFactJob, AiFactRematchEvent
from app.models.ai_operating_policy import AiProofAge
from app.services.ai_fact_coordinator import (
    FactCoordinatorCursor,
    FactCoordinatorUnavailable,
    OfflineFactCoordinator,
    SourceFactPolicy,
)
from app.services.ai_fact_quality import FactQualityPolicy

pytestmark = pytest.mark.integration
proofs = proof_fixture


@pytest_asyncio.fixture
async def coordinator(pipeline, proofs):
    service, sessions = pipeline
    service.operating_policy = FactQualityPolicy(price_max_age_seconds=60, policy_max_age_seconds=120,
                                                evidence_retention_seconds=3600)
    async with sessions() as session, session.begin():
        await (await session.connection()).run_sync(AiProofAge.__table__.create)
    return make_coordinator(service)


def make_coordinator(service, *, max_sources=2, max_jobs=2):
    return OfflineFactCoordinator(service, sources=(SourceFactPolicy(
        "synthetic", mapping(), builder, VERSION, 60, max_jobs, False),),
        max_sources=max_sources, max_reconcile=2, max_payload_bytes=131_072)


async def job_state(pipeline, job_id):
    async with pipeline[1]() as session:
        row = await session.get(AiFactJob, job_id)
        return row.status, row.attempts, row.canonical_listing_id


async def test_tick_prepares_proof_and_replay_has_no_duplicate_publication(pipeline, coordinator):
    job = await queue(pipeline)
    first = await coordinator.run_once(FactCoordinatorCursor())
    status, attempts, listing = await job_state(pipeline, job)
    assert (status, attempts) == ("succeeded", 1)
    assert first.observed == first.proofs_prepared == 1
    assert first.job_outcomes == ("succeeded", "no_claim")
    assert len(first.content_refresh_due) == 1  # missing capture timestamp is not made fresh
    assert await guard(coordinator.proofs, listing)
    async with pipeline[1]() as session:
        before = await session.scalar(select(func.count()).select_from(AiFactRematchEvent))
    second = await coordinator.run_once(FactCoordinatorCursor())
    assert second.job_outcomes == ("no_claim",)
    assert second.content_refresh_due == first.content_refresh_due
    async with pipeline[1]() as session:
        assert await session.scalar(select(func.count()).select_from(AiFactRematchEvent)) == before
        assert await session.scalar(text("SELECT last_success_at FROM external_listing_sources")) is None


async def test_source_and_job_bounds_resume_then_wrap(pipeline, coordinator):
    jobs = [await queue(pipeline) for _ in range(5)]
    cursor = FactCoordinatorCursor()
    scans = []
    for _ in range(3):
        tick = await coordinator.run_once(cursor)
        scans.append(tick.sources_scanned)
        assert len(tick.job_outcomes) <= 2
        assert tick.reconciled <= 4
        assert tick.proofs_prepared + tick.proofs_deferred == tick.reconciled
        cursor = tick.cursor
    assert scans == [2, 2, 1] and cursor.source_after is None
    for job in jobs:
        assert (await job_state(pipeline, job))[0] == "succeeded"


async def test_same_version_other_source_is_never_claimed(pipeline, coordinator):
    other = await queue(pipeline)
    async with pipeline[1]() as session, session.begin():
        await session.execute(text("UPDATE external_listing_sources SET source_name='other'"))
    own = await queue(pipeline)
    tick = await coordinator.run_once(FactCoordinatorCursor())
    assert tick.sources_scanned == 1 and tick.observed == 1
    assert (await job_state(pipeline, own))[:2] == ("succeeded", 1)
    assert (await job_state(pipeline, other))[1] == 0


async def test_source_renamed_after_scan_is_rejected_before_builder(pipeline, coordinator, monkeypatch):
    await queue(pipeline)
    capture = coordinator.reader.capture
    builds = []

    async def raced(source_id):
        async with pipeline[1]() as session, session.begin():
            await session.execute(text("UPDATE external_listing_sources SET source_name='other'"))
        return await capture(source_id)

    def should_not_build(snapshot):
        builds.append(snapshot)
        return builder(snapshot)

    policy = coordinator.sources["synthetic"]
    coordinator.sources["synthetic"] = SourceFactPolicy(policy.source_name, policy.mapping, should_not_build,
        policy.extractor_version, policy.content_max_age_seconds, policy.max_jobs, policy.retry_builder_failures)
    monkeypatch.setattr(coordinator.reader, "capture", raced)
    tick = await coordinator.run_once(FactCoordinatorCursor())
    assert tick.observed == 0 and tick.rejected == 1 and builds == []


@pytest.mark.parametrize("change", ["hidden", "retired", "deleted", "payload"])
async def test_next_tick_repairs_mutation_without_serving_old_proof(pipeline, coordinator, change):
    job = await queue(pipeline)
    await coordinator.run_once(FactCoordinatorCursor())
    _, _, listing = await job_state(pipeline, job)
    async with pipeline[1]() as session, session.begin():
        sql = {
            "hidden": "UPDATE listings SET status='hidden'",
            "retired": "UPDATE external_listing_sources SET current_status='missing'",
            "deleted": "DELETE FROM external_listing_sources",
            "payload": "UPDATE external_listing_sources SET raw_payload=jsonb_build_object('changed',true)",
        }[change]
        await session.execute(text(sql))
    assert not await guard(coordinator.proofs, listing)
    tick = await coordinator.run_once(FactCoordinatorCursor())
    if change == "payload":
        assert tick.job_outcomes[0] == "succeeded"
        assert await guard(coordinator.proofs, listing)
    elif change == "hidden":
        assert tick.proofs_deferred == 1 and not await guard(coordinator.proofs, listing)
    else:
        # A proof may certify the now-empty current projection. It must not
        # resurrect the removed source's facts or describe the old snapshot.
        projection = await coordinator.pipeline.read_current_projection(listing)
        assert projection is not None and not projection.features


async def test_unknown_commit_outcome_replays_previous_cursor_without_second_job(pipeline, coordinator, monkeypatch):
    job = await queue(pipeline)
    original = coordinator.proofs.prepare

    async def lost_ack(listing_id):
        await original(listing_id)
        raise RuntimeError("PRIVATE_PAYLOAD_NOT_FOR_SUPERVISOR")

    monkeypatch.setattr(coordinator.proofs, "prepare", lost_ack)
    with pytest.raises(FactCoordinatorUnavailable, match="^OFFLINE_FACT_COORDINATOR_UNAVAILABLE$") as error:
        await coordinator.run_once(FactCoordinatorCursor())
    assert error.value.__cause__ is None
    assert (await job_state(pipeline, job))[:2] == ("succeeded", 1)
    monkeypatch.setattr(coordinator.proofs, "prepare", original)
    tick = await coordinator.run_once(FactCoordinatorCursor())
    assert tick.proofs_prepared == 1 and tick.job_outcomes == ("no_claim",)
    assert (await job_state(pipeline, job))[:2] == ("succeeded", 1)


async def test_cancellation_is_not_acknowledged_as_a_tick(pipeline, coordinator, monkeypatch):
    await queue(pipeline)

    async def cancelled(*args, **kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(coordinator.pipeline, "observe", cancelled)
    with pytest.raises(asyncio.CancelledError):
        await coordinator.run_once(FactCoordinatorCursor())


async def test_expired_content_is_reported_after_proof_reprepare(pipeline, coordinator):
    await queue(pipeline)
    async with pipeline[1]() as session, session.begin():
        await session.execute(text("UPDATE external_listing_sources SET last_success_at=clock_timestamp()-interval '61 seconds'"))
        original = await session.scalar(text("SELECT last_success_at FROM external_listing_sources"))
    for _ in range(2):
        tick = await coordinator.run_once(FactCoordinatorCursor())
        assert len(tick.content_refresh_due) == 1
    async with pipeline[1]() as session:
        assert await session.scalar(text("SELECT last_success_at FROM external_listing_sources")) == original


async def test_unexpired_lease_is_deferred_then_recovered_with_new_fence(pipeline, coordinator):
    job = await queue(pipeline)
    claim = await pipeline[0].claim(extractor_version=VERSION, source_name="synthetic")
    tick = await coordinator.run_once(FactCoordinatorCursor())
    assert tick.job_outcomes == ("no_claim",) and tick.proofs_deferred == 1
    async with pipeline[1]() as session, session.begin():
        await session.execute(text("UPDATE ai_fact_jobs SET lease_until=clock_timestamp()-interval '1 second'"))
    tick = await coordinator.run_once(FactCoordinatorCursor())
    assert tick.job_outcomes[0] == "succeeded" and tick.proofs_prepared == 1
    async with pipeline[1]() as session:
        row = await session.get(AiFactJob, job)
        assert row.attempts == 2 and row.fence == claim.fence + 1


async def test_fresh_content_is_not_reported_as_due(pipeline, coordinator):
    await queue(pipeline)
    async with pipeline[1]() as session, session.begin():
        await session.execute(text("UPDATE external_listing_sources SET last_success_at=clock_timestamp()"))
    assert not (await coordinator.run_once(FactCoordinatorCursor())).content_refresh_due


@pytest.mark.parametrize("head", ["exhausted", "superseded"])
@pytest.mark.parametrize("concurrent", [False, True])
async def test_queue_cleanup_does_not_end_source_budget(pipeline, coordinator, head, concurrent):
    first = await queue(pipeline)
    second = await queue(pipeline)
    async with pipeline[1]() as session, session.begin():
        if head == "exhausted":
            await session.execute(text("UPDATE ai_fact_jobs SET attempts=2 WHERE id=:id"), {"id": first})
        else:
            await session.execute(text("UPDATE ai_fact_sources SET generation=generation+1 "
                "WHERE source_record_id=(SELECT source_record_id FROM ai_fact_jobs WHERE id=:id)"), {"id": first})
    if concurrent:
        await asyncio.gather(*(coordinator.run_once(FactCoordinatorCursor()) for _ in range(2)))
    else:
        await coordinator.run_once(FactCoordinatorCursor())
    assert (await job_state(pipeline, second))[:2] == ("succeeded", 1)


async def test_one_attempt_budget_reports_cleanup_then_next_tick_progresses(pipeline, coordinator):
    first, second = await queue(pipeline), await queue(pipeline)
    async with pipeline[1]() as session, session.begin():
        await session.execute(text("UPDATE ai_fact_jobs SET attempts=2 WHERE id=:id"), {"id": first})
    limited = make_coordinator(pipeline[0], max_jobs=1)
    assert (await limited.run_once(FactCoordinatorCursor())).job_outcomes == ("skipped_terminal",)
    assert (await job_state(pipeline, second))[0] == "pending"
    assert (await limited.run_once(FactCoordinatorCursor())).job_outcomes == ("succeeded",)


@pytest.mark.parametrize("name", ["idealista", "synthetic", "Idealista", "A" + "a" * 63])
async def test_valid_source_prefix_captures_and_runs_with_exact_case(pipeline, coordinator, name):
    from dataclasses import replace

    from app.services.ai_fact_coordinator import OfflineFactCoordinator
    await queue(pipeline)
    async with pipeline[1]() as session, session.begin():
        await session.execute(text("UPDATE external_listing_sources SET source_name=:name"), {"name": name})
    source = replace(next(iter(coordinator.sources.values())), source_name=name)
    valid = OfflineFactCoordinator(pipeline[0], sources=(source,), max_sources=2,
                                   max_reconcile=2, max_payload_bytes=131_072)
    result = await valid.run_once(FactCoordinatorCursor())
    assert result.observed == result.proofs_prepared == 1 and "succeeded" in result.job_outcomes


@pytest.mark.parametrize("limit", [0, 101, True])
async def test_configuration_rejects_unbounded_limits(pipeline, coordinator, limit):
    with pytest.raises(ValueError):
        make_coordinator(pipeline[0], max_sources=limit)
