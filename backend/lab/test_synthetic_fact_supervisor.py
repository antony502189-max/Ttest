"""Disposable local supervision journal; never opens a provider budget journal."""
import asyncio
import sqlite3
import subprocess
import sys
from dataclasses import replace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.engine import make_url

from app.repositories.ai_fact_pipeline import FactPipeline
from app.schemas.ai_fact_bridge import BridgeMapping
from app.schemas.ai_fact_pipeline import FactQueuePolicy
from app.schemas.ai_listing_facts import FactVocabulary
from app.services.ai_fact_coordinator import (
    FactCoordinatorCursor,
    FactCoordinatorTick,
    OfflineFactCoordinator,
    SourceFactPolicy,
)
from app.services.ai_fact_quality import FactQualityPolicy
from lab.ai_fact_supervisor import (
    StaleSupervisor,
    SupervisorPolicy,
    SupervisorUnavailable,
    SyntheticFactSupervisor,
    SyntheticSupervisorJournal,
    configuration_digest,
)

BUNDLE = "a" * 64
POLICY = SupervisorPolicy(10, 1, 5, 2, 8, 30, 10, 100)


class Clock:
    value = 1000.0

    def __call__(self):
        return self.value


def tick():
    return FactCoordinatorTick(FactCoordinatorCursor(uuid4(), uuid4()), 1, 1, 0, (uuid4(),),
                               ("succeeded",), 1, 1, 0)


def journal(tmp_path, *, config="b" * 64, policy=POLICY):
    return SyntheticSupervisorJournal(tmp_path / "DISPOSABLE-fact-supervisor-test.sqlite3",
                                       configuration_sha256=config, policy=policy)


@pytest.fixture
def harness(tmp_path):
    pipeline = Mock(spec=FactPipeline)
    pipeline.sessions = Mock()
    pipeline.sessions.kw = {"bind": Mock(url=make_url("postgresql+asyncpg://127.0.0.1/ai_facts_test_unit"))}
    pipeline.operating_policy = FactQualityPolicy(price_max_age_seconds=60, policy_max_age_seconds=120,
                                                 evidence_retention_seconds=3600)
    pipeline.policy = FactQueuePolicy(lease_seconds=60, max_attempts=2, retry_delay_seconds=1)
    pipeline.vocabulary = FactVocabulary(amenity_codes=frozenset(), catalog_other_codes=frozenset(),
                                         tenant_group_codes=frozenset(), municipality_zones=frozenset())
    pipeline.resolver_version = "fixture.v1"
    mapping = BridgeMapping(structured_fields={}, rented_unit_capacity_fields=frozenset(), text_capacity_scope=None,
                            structured_smoking_scopes={}, text_smoking_scopes={}, amenity_codes={})
    coordinator = OfflineFactCoordinator(pipeline, sources=(SourceFactPolicy("synthetic", mapping, Mock(),
        "fixture.v1", 60, 1, False),), max_sources=1, max_reconcile=1, max_payload_bytes=1024)
    coordinator.run_once = AsyncMock(return_value=tick())
    store = journal(tmp_path, config=configuration_digest(coordinator, builder_bundle_sha256=BUNDLE, catalog_identity_sha256="c" * 64))
    clock = Clock()
    return SyntheticFactSupervisor(coordinator, store, builder_bundle_sha256=BUNDLE, catalog_identity_sha256="c" * 64, clock=clock)


def test_atomic_checkpoint_receipt_survive_reopen(tmp_path):
    store = journal(tmp_path)
    claim = store.claim(1000)
    result = tick()
    store.complete(claim, result, 1001)
    reopened = journal(tmp_path)
    assert reopened.state().revision == 1 and reopened.state().cursor == result.cursor
    assert reopened.receipt(1)["content_refresh_due"] == [str(result.content_refresh_due[0])]
    assert reopened.state().last_success == 1001 and reopened.claim(1002) is None


def test_write_failure_rolls_back_receipt_and_checkpoint(tmp_path):
    store = journal(tmp_path)
    claim = store.claim(1000)
    with sqlite3.connect(store.path) as db:
        db.execute("CREATE TRIGGER fail_checkpoint BEFORE UPDATE OF revision ON supervisor "
                   "BEGIN SELECT RAISE(ABORT,'synthetic fault'); END")
    with pytest.raises(sqlite3.IntegrityError):
        store.complete(claim, tick(), 1001)
    assert store.state().revision == 0 and store.state().cursor == FactCoordinatorCursor()
    assert store.receipt(1) is None


def test_owner_lease_and_fence_prevent_stale_completion_or_failure(tmp_path):
    first, second = journal(tmp_path), journal(tmp_path)
    old = first.claim(1000)
    assert second.claim(1001) is None
    new = second.claim(1005)
    assert new.fence == old.fence + 1 and new.cursor == old.cursor
    for operation in (lambda: first.complete(old, tick(), 1006), lambda: first.fail(old, 1006, timeout=False)):
        with pytest.raises(StaleSupervisor):
            operation()
    second.complete(new, tick(), 1006)
    assert first.state().revision == 1


def test_backoff_is_durable_capped_and_preserves_cursor(tmp_path):
    store = journal(tmp_path)
    now = 1000
    for delay in (2, 4, 8, 8):
        claim = store.claim(now)
        store.fail(claim, now, timeout=False)
        store = journal(tmp_path)
        assert store.state().next_at == now + delay and store.state().last_success is None
        assert store.state().cursor == FactCoordinatorCursor() and store.claim(now) is None
        now += delay
    store.complete(store.claim(now), tick(), now)
    assert store.state().failures == 0 and store.state().failure_code is None


def test_receipt_capacity_fails_closed_without_losing_refresh_ids(tmp_path):
    store = journal(tmp_path, policy=replace(POLICY, max_receipts=1))
    result = tick()
    store.complete(store.claim(1000), result, 1000)
    with pytest.raises(SupervisorUnavailable, match="RECEIPTS_FULL"):
        store.claim(1010)
    assert store.state().revision == 1 and store.receipt(1)["content_refresh_due"]


def test_changed_configuration_cannot_reuse_checkpoint(tmp_path):
    store = journal(tmp_path)
    store.complete(store.claim(1000), tick(), 1000)
    with pytest.raises(ValueError, match="binding mismatch"):
        journal(tmp_path, config="c" * 64)
    with pytest.raises(ValueError, match="binding mismatch"):
        journal(tmp_path, policy=replace(POLICY, interval_seconds=20))
    assert journal(tmp_path).state().revision == 1


@pytest.mark.parametrize("filename", ["budget.sqlite3", "DISPOSABLE-budget.sqlite3", "supervisor.sqlite3"])
def test_non_supervisor_journals_are_refused_without_touching_them(tmp_path, filename):
    path = tmp_path / filename
    with pytest.raises(ValueError, match="disposable"):
        SyntheticSupervisorJournal(path, configuration_sha256=BUNDLE, policy=POLICY)
    assert not path.exists()


@pytest.mark.parametrize("field,value", [("deadline_seconds", 0), ("max_receipts", 10001),
    ("interval_seconds", True), ("lease_seconds", 1), ("max_backoff_seconds", 1), ("max_health_jobs", 1001)])
def test_invalid_supervisor_limits_are_rejected(field, value):
    with pytest.raises(ValueError):
        replace(POLICY, **{field: value})


async def test_finite_steps_and_schedule(harness):
    assert await harness.run_steps(steps=3) == ("committed", "deferred", "deferred")
    harness.coordinator.run_once.assert_awaited_once_with(FactCoordinatorCursor())
    harness.clock.value += 10
    old = harness.journal.state().cursor
    assert await harness.run_once() == "committed"
    harness.coordinator.run_once.assert_awaited_with(old)
    with pytest.raises(ValueError):
        await harness.run_steps(steps=101)


async def test_lost_ack_after_commit_does_not_erase_success_or_repeat_tick(harness, monkeypatch):
    original = harness.journal.complete

    def lost_ack(*args):
        original(*args)
        raise sqlite3.OperationalError("PRIVATE_SQL_NOT_FOR_OUTPUT")

    monkeypatch.setattr(harness.journal, "complete", lost_ack)
    with pytest.raises(SupervisorUnavailable, match="^SYNTHETIC_SUPERVISOR_UNAVAILABLE$") as error:
        await harness.run_once()
    assert error.value.__cause__ is None
    assert harness.journal.state().revision == 1 and harness.journal.state().failures == 0
    assert harness.journal.receipt(1) is not None and await harness.run_once() == "deferred"
    harness.coordinator.run_once.assert_awaited_once()


async def test_cooperative_deadline_persists_failure_without_checkpoint(harness):
    cancelled = asyncio.Event()

    async def blocked(cursor):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    harness.coordinator.run_once.side_effect = blocked
    with pytest.raises(SupervisorUnavailable):
        await harness.run_once()
    assert cancelled.is_set()
    state = harness.journal.state()
    assert state.failure_code == "TICK_DEADLINE" and state.failures == 1
    assert state.revision == 0 and harness.journal.receipt(1) is None


async def test_shutdown_leaves_lease_for_restart_without_false_success(harness):
    entered = asyncio.Event()

    async def blocked(cursor):
        entered.set()
        await asyncio.Event().wait()

    harness.coordinator.run_once.side_effect = blocked
    task = asyncio.create_task(harness.run_once())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert harness.journal.state().revision == 0 and harness.journal.state().lease_until is not None
    assert await harness.run_once() == "deferred"
    harness.clock.value += POLICY.lease_seconds
    harness.coordinator.run_once.side_effect = None
    assert await harness.run_once() == "committed"


def test_live_configuration_is_bound_not_just_caller_digest(harness):
    harness.coordinator.max_sources = 2
    with pytest.raises(ValueError, match="does not match"):
        SyntheticFactSupervisor(harness.coordinator, harness.journal, builder_bundle_sha256=BUNDLE, catalog_identity_sha256="c" * 64)


def test_real_process_exit_keeps_claim_for_lease_recovery(tmp_path):
    store = journal(tmp_path)
    code = """
import os, sys
from pathlib import Path
from lab.ai_fact_supervisor import SyntheticSupervisorJournal, SupervisorPolicy
store = SyntheticSupervisorJournal(Path(sys.argv[1]), configuration_sha256='b'*64,
    policy=SupervisorPolicy(10,1,5,2,8,30,10,100))
assert store.claim(1000) is not None
os._exit(23)
"""
    process = subprocess.run([sys.executable, "-c", code, str(store.path)], check=False,
                             capture_output=True, timeout=10)
    assert process.returncode == 23, process.stderr.decode()
    reopened = journal(tmp_path)
    assert reopened.state().revision == 0 and reopened.claim(1004) is None
    claim = reopened.claim(1005)
    assert claim.fence == 2 and claim.cursor == FactCoordinatorCursor()


def test_unknown_existing_database_is_not_modified(tmp_path):
    path = tmp_path / "DISPOSABLE-fact-supervisor-test.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE unrelated(value TEXT)")
        db.execute("INSERT INTO unrelated VALUES('unchanged')")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="not an owned"):
        journal(tmp_path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("url", ["postgresql+asyncpg://127.0.0.1/production", 
    "postgresql+asyncpg://example.invalid/ai_facts_test_fixture", "sqlite:///budget.sqlite3"])
def test_harness_rejects_non_disposable_catalog_before_running(harness, url):
    harness.coordinator.pipeline.sessions.kw["bind"].url = make_url(url)
    with pytest.raises(ValueError, match="disposable loopback"):
        configuration_digest(harness.coordinator, builder_bundle_sha256=BUNDLE, catalog_identity_sha256="c" * 64)


async def test_config_mutation_after_construction_cannot_run_with_old_checkpoint(harness):
    harness.coordinator.max_sources = 2
    with pytest.raises(SupervisorUnavailable):
        await harness.run_once()
    harness.coordinator.run_once.assert_not_awaited()
    assert harness.journal.state().revision == 0


async def test_return_after_deadline_is_not_acknowledged_even_without_async_cancellation(harness, monkeypatch):
    instants = iter((0.0, 2.0))
    monkeypatch.setattr("lab.ai_fact_supervisor.monotonic", lambda: next(instants))
    with pytest.raises(SupervisorUnavailable):
        await harness.run_once()
    assert harness.journal.state().revision == 0
    assert harness.journal.state().failure_code == "TICK_DEADLINE"


async def test_worker_policy_drift_is_refused_before_tick(harness):
    harness.coordinator.workers[0].retry_builder_failures = True
    with pytest.raises(SupervisorUnavailable):
        await harness.run_once()
    harness.coordinator.run_once.assert_not_awaited()
