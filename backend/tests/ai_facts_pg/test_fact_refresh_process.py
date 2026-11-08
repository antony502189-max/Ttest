"""Actual spawn/kill/restart at consumer reservation, mock dispatch and PG effect."""
import asyncio
import hashlib
import json
import multiprocessing
import time
from dataclasses import replace
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_fact_coordinator import make_coordinator
from test_fact_refresh import POLICY
from test_fact_refresh import coordinator as coordinator_fixture
from test_fact_refresh import proofs as proof_fixture
from test_fact_refresh import refresh_setup as refresh_fixture
from test_fact_supervision import POLICY as SUPERVISOR_POLICY
from test_query_proofs import guard

from app.repositories.ai_fact_pipeline import FactPipeline
from app.schemas.ai_fact_pipeline import FactQueuePolicy
from app.schemas.ai_listing_facts import FactVocabulary
from app.services.ai_fact_coordinator import FactCoordinatorCursor
from app.services.ai_fact_quality import FactQualityPolicy
from lab.ai_fact_process import run_isolated_tick
from lab.ai_fact_refresh import (
    OPERATIONS,
    REQUEST_BUDGETS,
    REQUEST_CLAIMS,
    SyntheticDetailRefresh,
    SyntheticDetailRefreshTick,
    SyntheticRefreshPolicy,
)
from lab.ai_fact_supervisor import SyntheticFactSupervisor, SyntheticSupervisorJournal, configuration_digest

pytestmark = pytest.mark.integration
refresh_setup = refresh_fixture
coordinator, proofs = coordinator_fixture, proof_fixture


def refresh_factory(url, schema, journal_path, source, listing, bundle, receipt, document, marker, phase):
    engine = create_async_engine(url, connect_args={"server_settings": {
        "search_path": schema, "lock_timeout": "5000", "statement_timeout": "10000"}})
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    pipeline = FactPipeline(sessions, FactQueuePolicy(lease_seconds=60, max_attempts=2, retry_delay_seconds=1),
        FactVocabulary(amenity_codes=frozenset({"test_wifi"}), catalog_other_codes=frozenset(),
            tenant_group_codes=frozenset(), municipality_zones=frozenset()), resolver_version="source-resolver.test.v1",
        operating_policy=FactQualityPolicy(price_max_age_seconds=60, policy_max_age_seconds=120, evidence_retention_seconds=3600))
    service = make_coordinator(pipeline)
    catalog = hashlib.sha256(schema.encode()).hexdigest()
    journal = SyntheticSupervisorJournal(Path(journal_path), policy=SUPERVISOR_POLICY,
        configuration_sha256=configuration_digest(service, builder_bundle_sha256="a" * 64, catalog_identity_sha256=catalog))
    supervisor = SyntheticFactSupervisor(service, journal, builder_bundle_sha256="a" * 64, catalog_identity_sha256=catalog)
    def block():
        Path(marker).write_text(phase, encoding="utf-8")
        while True:
            time.sleep(1)
    def response(request):
        with Path(marker + ".gets").open("a", encoding="utf-8") as output:
            output.write("GET\n")
        if phase == "http":
            block()
        return httpx.Response(200, json=json.loads(document))
    runner = SyntheticDetailRefresh(supervisor, policy=SyntheticRefreshPolicy(
        "synthetic", "example.invalid", 10, 131_072, 1, 10, 2, 30),
        cohort=((UUID(source), UUID(listing)),), transport=httpx.MockTransport(response), mock_bundle_sha256=bundle)
    if phase == "reserved":
        claim = runner._claim
        async def after_claim(*args):
            result = await claim(*args)
            block()
            return result
        runner._claim = after_claim
    if phase == "committed":
        write = runner._write
        async def after_commit(*args):
            result = await write(*args)
            block()
            return result
        runner._write = after_commit
    return SyntheticDetailRefreshTick(runner, revision=1, expected_digest=receipt)


@pytest.mark.parametrize("refresh_setup", [replace(POLICY, max_total_requests=2)], indirect=True)
@pytest.mark.parametrize("phase", ["reserved", "http", "committed"])
async def test_hard_kill_consumer_preserves_budget_fence_and_exact_effect(refresh_setup, pipeline, tmp_path, phase):
    runner, source, listing, _, document, _ = refresh_setup
    async with pipeline[1]() as session:
        schema = await session.scalar(text("SELECT current_schema()"))
    marker = str(tmp_path / "owned-refresh-phase")
    args = (pipeline[1].kw["bind"].url.render_as_string(hide_password=False), schema,
        str(tmp_path / "DISPOSABLE-fact-supervisor-pg.sqlite3"), str(source), str(listing), runner.mock_bundle_sha256,
        runner.supervisor.journal.receipt_digest(1), json.dumps(document), marker, phase)
    result = await asyncio.to_thread(run_isolated_tick, refresh_factory, args, deadline_seconds=5)
    assert result.outcome == "deadline" and result.exitcode != 0
    assert Path(marker).read_text(encoding="utf-8") == phase
    assert result.pid not in {process.pid for process in multiprocessing.active_children()}
    async with pipeline[1]() as session:
        assert await session.scalar(select(REQUEST_BUDGETS.c.used)) == 1
        assert await session.scalar(select(REQUEST_CLAIMS.c.status)) == {
            "reserved": "reserved", "http": "dispatched", "committed": "finished"}[phase]
        assert await session.scalar(select(func.count()).select_from(OPERATIONS)) == int(phase == "committed")
    normal = (*args[:-1], "normal")
    replay = await asyncio.to_thread(run_isolated_tick, refresh_factory, normal, deadline_seconds=5)
    assert replay.outcome == ("committed" if phase == "committed" else "deferred")
    async with pipeline[1]() as session, session.begin():
        await session.execute(update(REQUEST_CLAIMS).values(lease_until=func.clock_timestamp()))
    resumed = await asyncio.to_thread(run_isolated_tick, refresh_factory, normal, deadline_seconds=5)
    assert resumed.outcome == "committed"
    async with pipeline[1]() as session:
        assert await session.scalar(select(REQUEST_BUDGETS.c.used)) == (1 if phase == "committed" else 2)
        assert await session.scalar(select(func.count()).select_from(OPERATIONS)) == 1
    assert Path(marker + ".gets").read_text(encoding="utf-8").splitlines() == ["GET"] * (2 if phase == "http" else 1)
    tick = await runner.supervisor.coordinator.run_once(FactCoordinatorCursor())
    assert tick.proofs_prepared == 1 and await guard(runner.supervisor.coordinator.proofs, listing)
    assert runner.supervisor.journal.pending().refresh == 1  # no automatic ACK
