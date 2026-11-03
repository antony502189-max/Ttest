"""Supervisor journal + actual coordinator/queue/proofs on owned disposable PG."""
import hashlib
import sqlite3
import time
from dataclasses import replace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select, text
from test_fact_coordinator import coordinator as coordinator_fixture
from test_offline_fact_worker import queue
from test_query_proofs import proofs as proof_fixture

from app.models.ai_fact_pipeline import AiFactJob, AiFactRematchEvent
from lab.ai_fact_supervisor import (
    SupervisorPolicy,
    SupervisorUnavailable,
    SyntheticFactSupervisor,
    SyntheticSupervisorJournal,
    configuration_digest,
)

pytestmark = pytest.mark.integration
coordinator = coordinator_fixture
proofs = proof_fixture
BUNDLE = "a" * 64  # Identity of this explicit synthetic builder fixture, no provider.
POLICY = SupervisorPolicy(10, 5, 10, 2, 8, 30, 20, 100)


async def supervisor(tmp_path, coordinator, *, policy=POLICY, clock=time.time):
    async with coordinator.pipeline.sessions() as session:
        schema = await session.scalar(text("SELECT current_schema()"))
    catalog = hashlib.sha256(schema.encode()).hexdigest()
    digest = configuration_digest(coordinator, builder_bundle_sha256=BUNDLE, catalog_identity_sha256=catalog)
    journal = SyntheticSupervisorJournal(tmp_path / "DISPOSABLE-fact-supervisor-pg.sqlite3",
                                         configuration_sha256=digest, policy=policy)
    return SyntheticFactSupervisor(coordinator, journal, builder_bundle_sha256=BUNDLE,
                                    catalog_identity_sha256=catalog, clock=clock)


async def test_real_tick_restarts_from_durable_cursor_and_retains_refresh_receipt(pipeline, coordinator, tmp_path):
    await queue(pipeline)
    runner = await supervisor(tmp_path, coordinator)
    assert await runner.run_once() == "committed"
    restarted = await supervisor(tmp_path, coordinator)
    assert restarted.journal.state().revision == 1
    assert restarted.journal.receipt(1)["content_refresh_due"]
    assert await restarted.run_once() == "deferred"
    health = await restarted.health()
    assert health.content_refresh_due == 1 and health.attention and not health.stale


async def test_lost_ack_after_real_job_and_proof_does_not_repeat_extraction(pipeline, coordinator, tmp_path, monkeypatch):
    job = await queue(pipeline)
    runner = await supervisor(tmp_path, coordinator)
    original = runner.journal.complete

    def lost_ack(*args):
        original(*args)
        raise RuntimeError("PRIVATE_ACK_FAILURE")

    monkeypatch.setattr(runner.journal, "complete", lost_ack)
    with pytest.raises(SupervisorUnavailable):
        await runner.run_once()
    restarted = await supervisor(tmp_path, coordinator, clock=lambda: time.time() + 11)
    async with pipeline[1]() as session:
        events = await session.scalar(select(func.count()).select_from(AiFactRematchEvent))
    assert await restarted.run_once() == "committed"
    async with pipeline[1]() as session:
        row = await session.get(AiFactJob, job)
        assert row.status == "succeeded" and row.attempts == 1
        assert await session.scalar(select(func.count()).select_from(AiFactRematchEvent)) == events
    assert restarted.journal.state().revision == 2


async def test_terminal_job_is_attention_even_after_successful_supervisor_tick(pipeline, coordinator, tmp_path):
    await queue(pipeline)

    def fails(snapshot):
        raise RuntimeError("PRIVATE_BUILDER_PAYLOAD")

    coordinator.sources["synthetic"] = replace(coordinator.sources["synthetic"], builder=fails)
    coordinator.workers[0].builder = fails  # Explicit injected synthetic builder, before journal binding.
    runner = await supervisor(tmp_path, coordinator)
    assert await runner.run_once() == "committed"
    health = await runner.health()
    assert health.terminal_jobs == 1 and health.deferred_proofs == 1 and health.attention
    assert health.consecutive_failures == 0 and not health.stale
    assert "PRIVATE" not in repr(health)


async def test_expired_queue_lease_and_exhaustion_are_visible(pipeline, coordinator, tmp_path):
    await queue(pipeline)
    await pipeline[0].claim()
    async with pipeline[1]() as session, session.begin():
        await session.execute(text("UPDATE ai_fact_jobs SET attempts=2,lease_until=clock_timestamp()-interval '1 second'"))
    runner = await supervisor(tmp_path, coordinator)
    assert (await runner.health()).expired_leases == 1
    assert await runner.run_once() == "committed"
    health = await runner.health()
    assert health.terminal_jobs == 1 and health.expired_leases == 0 and health.attention


async def test_health_sample_is_bounded_and_never_calls_truncation_healthy(pipeline, coordinator, tmp_path):
    for _ in range(5):
        await queue(pipeline)
    runner = await supervisor(tmp_path, coordinator, policy=replace(POLICY, max_health_jobs=1))
    assert await runner.run_once() == "committed"
    health = await runner.health()
    assert health.sample_truncated and health.attention


async def test_fresh_success_can_be_healthy_but_later_staleness_requires_attention(pipeline, coordinator, tmp_path):
    await queue(pipeline)
    async with pipeline[1]() as session, session.begin():
        await session.execute(text("UPDATE external_listing_sources SET last_success_at=clock_timestamp()"))
    runner = await supervisor(tmp_path, coordinator)
    assert await runner.run_once() == "committed"
    health = await runner.health()
    assert not health.attention and not health.stale
    runner.clock = lambda: time.time() + 31
    assert (await runner.health()).stale


async def test_health_storage_failure_is_redacted(pipeline, coordinator, tmp_path, monkeypatch):
    runner = await supervisor(tmp_path, coordinator)
    monkeypatch.setattr(runner, "_health", AsyncMock(side_effect=RuntimeError("PRIVATE_SQL_PAYLOAD")))
    with pytest.raises(SupervisorUnavailable, match="^SYNTHETIC_SUPERVISOR_HEALTH_UNAVAILABLE$") as error:
        await runner.health()
    assert error.value.__cause__ is None


async def test_checkpoint_rollback_after_real_job_replays_without_duplicate_job(pipeline, coordinator, tmp_path):
    job = await queue(pipeline)
    runner = await supervisor(tmp_path, coordinator)
    with sqlite3.connect(runner.journal.path) as db:
        db.execute("CREATE TRIGGER fail_checkpoint BEFORE UPDATE OF revision ON supervisor "
                   "BEGIN SELECT RAISE(ABORT,'synthetic fault'); END")
    with pytest.raises(SupervisorUnavailable):
        await runner.run_once()
    assert runner.journal.state().revision == 0 and runner.journal.receipt(1) is None
    with sqlite3.connect(runner.journal.path) as db:
        db.execute("DROP TRIGGER fail_checkpoint")
    restarted = await supervisor(tmp_path, coordinator, clock=lambda: time.time() + 3)
    assert await restarted.run_once() == "committed"
    async with pipeline[1]() as session:
        row = await session.get(AiFactJob, job)
        assert row.status == "succeeded" and row.attempts == 1
    assert restarted.journal.receipt(1)["job_outcomes"] == ["no_claim"]


async def test_retry_queue_is_visible_and_other_source_failures_do_not_leak(pipeline, coordinator, tmp_path):
    own = await queue(pipeline)
    other = await queue(pipeline)
    async with pipeline[1]() as session, session.begin():
        await session.execute(text("UPDATE ai_fact_jobs SET attempts=1 WHERE id=:id"), {"id": own})
        await session.execute(text("UPDATE ai_fact_jobs SET status='failed' WHERE id=:id"), {"id": other})
        await session.execute(text("UPDATE external_listing_sources SET source_name='other' "
                                   "WHERE id=(SELECT source_record_id FROM ai_fact_jobs WHERE id=:id)"), {"id": other})
    runner = await supervisor(tmp_path, coordinator)
    health = await runner.health()
    assert health.pending_jobs == health.retry_jobs == 1 and health.terminal_jobs == 0 and health.attention


async def test_capacity_is_attention_even_with_fresh_success(pipeline, coordinator, tmp_path):
    await queue(pipeline)
    async with pipeline[1]() as session, session.begin():
        await session.execute(text("UPDATE external_listing_sources SET last_success_at=clock_timestamp()"))
    runner = await supervisor(tmp_path, coordinator, policy=replace(POLICY, max_receipts=1))
    assert await runner.run_once() == "committed"
    health = await runner.health()
    assert health.receipt_capacity_reached and health.attention and not health.stale
