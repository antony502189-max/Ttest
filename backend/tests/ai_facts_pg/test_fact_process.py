"""Hard process death in real coordinator work on owned disposable PostgreSQL."""

import asyncio
import multiprocessing
import sqlite3
import time
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_fact_coordinator import coordinator, proofs  # noqa: F401 -- fixture dependencies
from test_offline_fact_worker import VERSION, builder, mapping, queue

from app.models.ai_fact_pipeline import AiFactJob, AiFactRematchEvent
from app.repositories.ai_fact_pipeline import FactPipeline
from app.schemas.ai_fact_pipeline import FactJobClaim, FactQueuePolicy, StaleFactWorker
from app.schemas.ai_listing_facts import FactVocabulary
from app.services.ai_fact_coordinator import OfflineFactCoordinator, SourceFactPolicy
from app.services.ai_fact_quality import FactQualityPolicy
from lab.ai_fact_process import run_isolated_tick
from lab.ai_fact_supervisor import (
    StaleSupervisor,
    SupervisorClaim,
    SupervisorPolicy,
    SyntheticFactSupervisor,
    SyntheticSupervisorJournal,
    configuration_digest,
)

pytestmark = pytest.mark.integration
POLICY = SupervisorPolicy(1, 20, 30, 1, 2, 60, 10, 100)
BUNDLE, CATALOG = "a" * 64, "b" * 64


def make_supervisor(url, schema, path, marker, mode, now):
    # Spawn creates independent connections; never fork the parent's pool.
    engine = create_async_engine(url, connect_args={"server_settings": {
        "search_path": schema, "statement_timeout": "10000", "lock_timeout": "5000"}})
    pipeline = FactPipeline(async_sessionmaker(engine, expire_on_commit=False),
        FactQueuePolicy(lease_seconds=60, max_attempts=2, retry_delay_seconds=1),
        FactVocabulary(amenity_codes=frozenset({"test_wifi"}), catalog_other_codes=frozenset(),
                       tenant_group_codes=frozenset(), municipality_zones=frozenset()),
        resolver_version="source-resolver.test.v1",
        operating_policy=FactQualityPolicy(price_max_age_seconds=60, policy_max_age_seconds=120,
                                          evidence_retention_seconds=3600))
    calls = 0

    def block():
        Path(marker).write_text(mode, encoding="utf-8")
        # Real synchronous work which cannot observe asyncio cancellation.
        while True:
            time.sleep(1)

    def build(snapshot):
        nonlocal calls
        calls += 1
        if mode == "builder" and calls == 2:  # capture first, then worker after PG claim
            block()
        return builder(snapshot)

    service = OfflineFactCoordinator(pipeline, sources=(SourceFactPolicy(
        "synthetic", mapping(), build, VERSION, 60, 2, False),),
        max_sources=1, max_reconcile=2, max_payload_bytes=131_072)
    store = SyntheticSupervisorJournal(Path(path), policy=POLICY, configuration_sha256=configuration_digest(
        service, builder_bundle_sha256=BUNDLE, catalog_identity_sha256=CATALOG))
    if mode == "published":
        prepare = service.proofs.prepare

        async def after_publication(listing):
            result = await prepare(listing)
            block()
            return result

        service.proofs.prepare = after_publication
    if mode == "receipt":
        complete = store.complete

        def lost_ack(*args):
            complete(*args)
            block()

        store.complete = lost_ack
    return SyntheticFactSupervisor(service, store, builder_bundle_sha256=BUNDLE,
                                   catalog_identity_sha256=CATALOG, clock=lambda: now)


@pytest.mark.parametrize("mode", ["builder", "published", "receipt"])
@pytest.mark.usefixtures("coordinator")
async def test_deadline_kills_work_and_restart_recovers_without_duplicate_publication(
        pipeline, pg, tmp_path, mode):
    job_id = await queue(pipeline)
    with pg[0].connect() as connection:
        schema = connection.scalar(text("SELECT current_schema()"))
    url = pipeline[1].kw["bind"].url.render_as_string(hide_password=False)
    path = tmp_path / "DISPOSABLE-fact-supervisor-process.sqlite3"
    marker = tmp_path / "interrupted-phase"
    args = (url, schema, str(path), str(marker), mode, 1000)
    started = time.monotonic()
    result = await asyncio.to_thread(run_isolated_tick, make_supervisor, args, deadline_seconds=5)
    assert result.outcome == "deadline" and result.exitcode != 0
    assert time.monotonic() - started < 12
    assert marker.read_text(encoding="utf-8") == mode  # proved actual work reached, not just spawn timeout
    assert result.pid not in {p.pid for p in multiprocessing.active_children()}

    normal = (*args[:4], "normal", 1001)
    supervisor = make_supervisor(*normal)
    store = supervisor.journal
    before = store.state()
    assert before.revision == (1 if mode == "receipt" else 0)
    assert store.receipt_count() == before.revision
    assert store.pending().receipts == (1 if mode == "receipt" else 0)
    assert (before.cursor.source_after is not None) == (mode == "receipt")
    receipt_digest = store.receipt_digest(1) if mode == "receipt" else None
    with sqlite3.connect(path) as db:
        revision, fence, owner = db.execute("SELECT revision,fence,owner FROM supervisor").fetchone()
    stale = SupervisorClaim(revision, fence, owner, before.cursor)
    deferred = await asyncio.to_thread(run_isolated_tick, make_supervisor, normal, deadline_seconds=5)
    assert deferred.outcome == ("deferred" if mode != "receipt" else "committed")
    async with pipeline[1]() as session:
        row = await session.get(AiFactJob, job_id)
        old_fence = row.fence
        if mode == "builder":
            assert row.status == "running" and row.attempts == 1 and row.lease_until is not None
            claim = FactJobClaim.model_validate({name: getattr(row, "id" if name == "job_id" else name)
                for name in FactJobClaim.model_fields})
        else:
            assert row.status == "succeeded" and row.attempts == 1
        events_before = await session.scalar(select(func.count()).select_from(AiFactRematchEvent))
    if mode == "builder":
        # Accelerate only this owned synthetic PG lease; production clocks are untouched.
        async with pipeline[1]() as session, session.begin():
            await session.execute(text("UPDATE ai_fact_jobs SET lease_until=clock_timestamp()-interval '1 second'"))
    recovered = await asyncio.to_thread(run_isolated_tick, make_supervisor,
        (*args[:4], "normal", 1031), deadline_seconds=5)
    assert recovered.outcome == "committed"
    reopened = make_supervisor(*normal).journal
    assert reopened.state().revision == (3 if mode == "receipt" else 1)
    assert reopened.receipt_count() == reopened.state().revision
    if receipt_digest:
        assert reopened.receipt_digest(1) == receipt_digest
        assert reopened.receipt(1)["content_refresh_due"]
    else:
        assert reopened.receipt(1)["cursor"]["source_after"] is not None
    with pytest.raises(StaleSupervisor):
        reopened.fail(stale, 1031, timeout=True)
    async with pipeline[1]() as session:
        row = await session.get(AiFactJob, job_id)
        assert row.status == "succeeded" and row.lease_until is None
        assert row.attempts == (2 if mode == "builder" else 1)
        assert row.fence == old_fence + (1 if mode == "builder" else 0)
        events = await session.scalar(select(func.count()).select_from(AiFactRematchEvent))
        if mode != "builder":
            assert events == events_before
    # All committed refresh signals remain durable until an exact explicit ack.
    assert reopened.pending().refresh >= 1
    if mode == "builder":
        with pytest.raises(StaleFactWorker):
            await pipeline[0].fail(claim, retryable=False, code="EXTRACTOR_FAILED")
    replay = await asyncio.to_thread(run_isolated_tick, make_supervisor,
        (*args[:4], "normal", 1032), deadline_seconds=5)
    assert replay.outcome == "committed"
    async with pipeline[1]() as session:
        assert await session.scalar(select(func.count()).select_from(AiFactRematchEvent)) == events
        row = await session.get(AiFactJob, job_id)
        assert row.attempts == (2 if mode == "builder" else 1)
