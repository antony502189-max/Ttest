import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.models.ai_fact_pipeline import AiFactJob, AiFactRematchEvent
from app.models.ai_listing_facts import AiListingFact
from app.repositories.ai_fact_pipeline import FactPipeline
from app.repositories.ai_fact_snapshots import FactSnapshotReader
from app.schemas.ai_fact_bridge import BridgeMapping, ParserEvidencePacket
from app.schemas.ai_fact_pipeline import FactQueuePolicy
from app.services.ai_fact_bridge import prepare_captured_source
from app.services.ai_offline_fact_worker import OfflineFactJobRunner, OfflineFactStorageError

pytestmark = pytest.mark.integration
CASES = json.loads((Path(__file__).parents[1] / "fixtures/ai_fact_bridge/parser-373-synthetic.json").read_text(encoding="utf-8"))
VERSION = "offline-fixture.v1"


def mapping():
    return BridgeMapping(structured_fields={}, rented_unit_capacity_fields=frozenset(), text_capacity_scope=None,
                         structured_smoking_scopes={}, text_smoking_scopes={}, amenity_codes={})


def builder(snapshot):
    data = json.loads(snapshot.normalized_json)["packet"]
    data.update(source_identifier=snapshot.reference.source_identifier,
                canonical_listing_identifier=str(snapshot.reference.canonical_listing_id))
    return ParserEvidencePacket.model_validate_json(json.dumps(data))


def runner(pipeline, *, build=builder, version=VERSION, retry=False):
    service, sessions = pipeline
    return OfflineFactJobRunner(service, FactSnapshotReader(sessions, max_payload_bytes=131_072),
        builder=build, mapping=mapping(), extractor_version=version, retry_builder_failures=retry)


async def queue(pipeline, *, version=VERSION):
    service, sessions = pipeline
    source, listing = uuid4(), uuid4()
    packet = next(c["packet"] for c in CASES["cases"] if c["name"] == "pets_deny")
    async with sessions() as session, session.begin():
        await session.execute(text("INSERT INTO listings(id,status) VALUES(:id,'published')"), {"id": listing})
        await session.execute(text("INSERT INTO external_listing_sources "
                                   "(id,canonical_listing_id,fingerprint,current_status,normalized_payload) "
                                   "VALUES(:id,:listing,:hash,'active',CAST(:payload AS jsonb))"),
                              {"id": source, "listing": listing, "hash": "c" * 64, "payload": json.dumps({"packet": packet})})
    ready = await prepare_captured_source(FactSnapshotReader(sessions, max_payload_bytes=131_072), source,
        builder=builder, mapping=mapping(), vocabulary=service.vocabulary, extractor_version=version)
    return await service.observe(ready.source)


async def count(pipeline, model):
    async with pipeline[1]() as session:
        return await session.scalar(select(func.count()).select_from(model))


async def test_run_once_commits_one_job_and_no_claim_does_not_build(pipeline):
    job = await queue(pipeline)
    worker = runner(pipeline)
    success = await worker.run_once()
    assert success.outcome == "succeeded" and success.job_id == job
    assert success.receipt.status == "succeeded"
    assert (await worker.run_once()).outcome == "no_claim"
    assert await count(pipeline, AiListingFact) == 4
    assert await count(pipeline, AiFactRematchEvent) == 2


async def test_concurrent_runners_invoke_builder_only_once(pipeline):
    await queue(pipeline)
    calls = []

    def counted(snapshot):
        calls.append(snapshot.reference.source_record_id)
        return builder(snapshot)

    worker = runner(pipeline, build=counted)
    results = await asyncio.gather(*(worker.run_once() for _ in range(8)))
    assert sum(r.outcome == "succeeded" for r in results) == 1
    assert len(calls) == 1
    assert await count(pipeline, AiFactRematchEvent) == 2


async def test_extractor_version_filter_does_not_fail_other_deployments_jobs(pipeline):
    _, sessions = pipeline
    other = await queue(pipeline, version="other-fixture.v1")
    own = await queue(pipeline)
    result = await runner(pipeline).run_once()
    assert result.job_id == own
    assert (await runner(pipeline, version="unknown-fixture.v1").run_once()).outcome == "no_claim"
    async with sessions() as session:
        remaining = await session.get(AiFactJob, other)
        assert remaining.status == "pending" and remaining.attempts == 0


@pytest.mark.parametrize("retry", [False, True])
async def test_builder_error_is_redacted_with_explicit_retry_policy(pipeline, retry):
    _, sessions = pipeline
    job = await queue(pipeline)

    def failing(snapshot):
        raise RuntimeError("PRIVATE_FIXTURE_ERROR_DO_NOT_EXPOSE" + snapshot.normalized_json)

    result = await runner(pipeline, build=failing, retry=retry).run_once()
    assert result.outcome == ("retry_scheduled" if retry else "failed")
    assert result.failure_code == "EXTRACTOR_FAILED"
    assert "PRIVATE_FIXTURE_ERROR" not in repr(result)
    assert await count(pipeline, AiListingFact) == 0
    async with sessions() as session:
        row = await session.get(AiFactJob, job)
        assert row.failure_code == "EXTRACTOR_FAILED" and row.lease_until is None


async def test_retry_budget_and_delay_remain_authoritative_in_pg(pipeline):
    _, sessions = pipeline
    await queue(pipeline)

    def failing(snapshot):
        raise RuntimeError("synthetic builder failure")

    worker = runner(pipeline, build=failing, retry=True)
    assert (await worker.run_once()).outcome == "retry_scheduled"
    assert (await worker.run_once()).outcome == "no_claim"
    async with sessions() as session, session.begin():
        await session.execute(text("UPDATE ai_fact_jobs SET available_at=clock_timestamp()-interval '1 second'"))
    assert (await worker.run_once()).outcome == "failed"
    assert (await worker.run_once()).outcome == "no_claim"


async def test_invalid_packet_is_not_retried_as_transient_builder_failure(pipeline):
    await queue(pipeline)

    def invalid(snapshot):
        return ParserEvidencePacket.model_validate(builder(snapshot).model_dump() | {"content_hash": "0" * 64})

    result = await runner(pipeline, build=invalid, retry=True).run_once()
    assert result.outcome == "failed" and result.failure_code == "INVALID_RESULT"
    assert await count(pipeline, AiListingFact) == 0


@pytest.mark.parametrize("change", ["payload", "retire", "hidden"])
async def test_changed_source_is_reconciled_without_stale_publication(pipeline, change):
    _, sessions = pipeline
    job = await queue(pipeline)
    async with sessions() as session, session.begin():
        if change == "payload":
            await session.execute(text("UPDATE external_listing_sources SET raw_payload=jsonb_build_object('changed',true)"))
        elif change == "retire":
            await session.execute(text("UPDATE external_listing_sources SET current_status='missing'"))
        else:
            await session.execute(text("UPDATE listings SET status='hidden'"))
    result = await runner(pipeline).run_once()
    assert result.outcome == ("failed" if change == "hidden" else "stale")
    assert await count(pipeline, AiListingFact) == 0
    async with sessions() as session:
        assert (await session.get(AiFactJob, job)).status == ("failed" if change == "hidden" else "superseded")


async def test_builder_holds_no_source_lock_and_late_source_change_is_rejected(pipeline, pg):
    await queue(pipeline)
    sync_engine, _ = pg

    def mutate_after_capture(snapshot):
        with sync_engine.begin() as connection:
            connection.execute(text("SELECT id FROM external_listing_sources FOR UPDATE NOWAIT"))
            connection.execute(text("UPDATE external_listing_sources SET raw_payload=jsonb_build_object('changed',true)"))
        return builder(snapshot)

    result = await runner(pipeline, build=mutate_after_capture).run_once()
    assert result.outcome == "stale" and result.receipt.status == "superseded"
    assert await count(pipeline, AiListingFact) == 0


async def test_cancellation_keeps_lease_for_bounded_crash_recovery(pipeline):
    _, sessions = pipeline
    job = await queue(pipeline)

    def cancel(snapshot):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await runner(pipeline, build=cancel).run_once()
    async with sessions() as session, session.begin():
        assert (await session.get(AiFactJob, job)).status == "running"
        await session.execute(text("UPDATE ai_fact_jobs SET lease_until=clock_timestamp()-interval '1 second'"))
    assert (await runner(pipeline).run_once()).outcome == "succeeded"
    async with sessions() as session:
        assert (await session.get(AiFactJob, job)).fence == 2


async def test_write_failure_is_redacted_and_does_not_fake_a_terminal_receipt(pipeline):
    _, sessions = pipeline
    job = await queue(pipeline)
    async with sessions() as session, session.begin():
        await session.execute(text("CREATE FUNCTION worker_write_failure() RETURNS trigger LANGUAGE plpgsql AS $$ "
                                   "BEGIN RAISE EXCEPTION 'PRIVATE_FIXTURE_SQL_ERROR'; END $$"))
        await session.execute(text("CREATE TRIGGER worker_write_failure BEFORE INSERT ON ai_fact_rematch_events "
                                   "FOR EACH ROW EXECUTE FUNCTION worker_write_failure()"))
    with pytest.raises(OfflineFactStorageError) as error:
        await runner(pipeline).run_once()
    assert str(error.value) == "OFFLINE_FACT_STORAGE_UNAVAILABLE"
    assert "PRIVATE_FIXTURE_SQL_ERROR" not in repr(error.value)
    assert await count(pipeline, AiListingFact) == 0
    assert await count(pipeline, AiFactRematchEvent) == 1
    async with sessions() as session:
        assert (await session.get(AiFactJob, job)).status == "running"


async def test_unknown_commit_ack_does_not_cause_second_inference(pipeline, monkeypatch):
    service, _ = pipeline
    await queue(pipeline)
    complete = service.complete
    calls = []

    def counted(snapshot):
        calls.append(1)
        return builder(snapshot)

    async def committed_but_lost_ack(*args, **kwargs):
        await complete(*args, **kwargs)
        raise SQLAlchemyError("PRIVATE_FIXTURE_ACK_ERROR")

    monkeypatch.setattr(service, "complete", committed_but_lost_ack)
    with pytest.raises(OfflineFactStorageError):
        await runner(pipeline, build=counted).run_once()
    monkeypatch.setattr(service, "complete", complete)
    assert (await runner(pipeline, build=counted).run_once()).outcome == "no_claim"
    assert len(calls) == 1
    assert await count(pipeline, AiFactRematchEvent) == 2


async def test_expired_builder_cannot_commit_facts(pipeline, pg):
    service, sessions = pipeline
    await queue(pipeline)
    short = FactPipeline(sessions, FactQueuePolicy(lease_seconds=1, max_attempts=2, retry_delay_seconds=1),
                         service.vocabulary, resolver_version=service.resolver_version)
    sync_engine, _ = pg

    def slow(snapshot):
        with sync_engine.begin() as connection:
            connection.execute(text("SELECT pg_sleep(1.2)"))
        return builder(snapshot)

    result = await runner((short, sessions), build=slow).run_once()
    assert result.outcome == "stale"
    assert await count(pipeline, AiListingFact) == 0
