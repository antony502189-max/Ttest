"""Real queue transactions with synthetic legacy rows and a handwritten fake extractor."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError

from app.models.ai_fact_pipeline import AiFactCatalog, AiFactJob, AiFactRematchEvent, AiFactSource
from app.models.ai_listing_facts import AiListingFact, AiListingFactBatch, AiListingSearchFeatures
from app.repositories.ai_fact_pipeline import FactPipeline
from app.schemas.ai_fact_pipeline import (
    FactQueuePolicy,
    FactResultConflict,
    SourceIdentityConflict,
    SourceInput,
    StaleFactWorker,
)
from app.schemas.ai_listing_facts import FactBatch, digest

pytestmark = pytest.mark.integration


async def seed(pipeline, *, listing_id=None, description="Pets allowed"):
    service, sessions = pipeline
    listing_id, source_id = listing_id or uuid4(), uuid4()
    async with sessions() as session, session.begin():
        await session.execute(text("INSERT INTO listings(id,status) VALUES (:id,'published') ON CONFLICT DO NOTHING"), {"id": listing_id})
        await session.execute(text("INSERT INTO external_listing_sources "
                                   "(id,canonical_listing_id,fingerprint,current_status,last_success_at,content_updated_at) "
                                   "VALUES (:id,:listing,:hash,'active',clock_timestamp(),clock_timestamp() - interval '1 day')"),
                              {"id": source_id, "listing": listing_id, "hash": digest(description)})
        _, authority = await service._authority(session, listing_id)
        snapshot_hash = authority[source_id].snapshot_hash
    return SourceInput(source_record_id=source_id, canonical_listing_id=listing_id,
                       content_hash=digest({"description": description}), schema_version="ai-facts.v1",
                       snapshot_hash=snapshot_hash,
                       taxonomy_version="ai-search.v1", extractor_version="fake.v1")


def fake_extract(claim, *, allow=True, description=None):
    description = description or ("Pets allowed" if allow else "No pets")
    return FactBatch.model_validate({
        "schema_version": claim.schema_version, "taxonomy_version": claim.taxonomy_version,
        "batch_id": uuid4(), "canonical_listing_id": claim.canonical_listing_id, "source_record_id": claim.source_record_id,
        "source_generation": claim.generation, "content_hash": claim.content_hash, "extractor_version": claim.extractor_version,
        "observed_at": datetime.now(UTC), "source_status": "active", "last_successful_check_at": None,
        "last_content_change_at": None, "last_check_error_at": None,
        "facts": [{"fact_id": uuid4(), "key": "pets", "status": "explicit_allow" if allow else "explicit_deny",
                   "typed_value": {"kind": "policy", "allowed": allow}, "qualifiers": {}, "origin": "source_text",
                   "evidence": [{"field": "description", "quote": description, "start": 0, "end": len(description)}]}],
    })


async def features(pipeline, listing_id):
    _, sessions = pipeline
    async with sessions() as session:
        value = await session.get(AiListingSearchFeatures, listing_id)
        return value.features


async def count(pipeline, model):
    async with pipeline[1]() as session:
        return await session.scalar(select(func.count()).select_from(model))


async def test_concurrent_observe_and_claim_are_idempotent(pipeline):
    service, _ = pipeline
    source = await seed(pipeline)
    jobs = await asyncio.gather(*(service.observe(source) for _ in range(12)))
    assert len(set(jobs)) == 1
    assert await count(pipeline, AiFactJob) == 1
    assert await count(pipeline, AiFactRematchEvent) == 1
    claims = await asyncio.gather(*(service.claim() for _ in range(12)))
    assert len([c for c in claims if c is not None]) == 1


async def test_fake_worker_completes_and_terminal_replay_does_not_republish(pipeline):
    service, sessions = pipeline
    source = await seed(pipeline)
    await service.observe(source)
    claim = await service.claim()
    result = fake_extract(claim)
    receipt = await service.complete(claim, result, {"description": "Pets allowed"})
    assert receipt.status == "succeeded"
    assert await service.complete(claim, result, {"description": "Pets allowed"}) == receipt
    assert await count(pipeline, AiListingFact) == 1
    assert await count(pipeline, AiFactRematchEvent) == 2
    assert (await features(pipeline, source.canonical_listing_id))[0]["status"] == "explicit_allow"
    async with sessions() as session:
        batch = await session.get(AiListingFactBatch, claim.job_id)
        assert batch.last_content_change_at < batch.last_successful_check_at
    altered = result.model_dump()
    altered["facts"][0]["status"] = "explicit_deny"
    altered["facts"][0]["typed_value"]["allowed"] = False
    with pytest.raises(FactResultConflict):
        await service.complete(claim, FactBatch.model_validate(altered), {"description": "Pets allowed"})


async def test_pending_source_barrier_then_conflict_not_last_writer(pipeline):
    service, _ = pipeline
    a = await seed(pipeline)
    b = await seed(pipeline, listing_id=a.canonical_listing_id, description="No pets")
    await service.observe(a)
    claim_a = await service.claim()
    await service.complete(claim_a, fake_extract(claim_a), {"description": "Pets allowed"})
    assert await features(pipeline, a.canonical_listing_id) == []
    await service.observe(b)
    claim_b = await service.claim()
    await service.complete(claim_b, fake_extract(claim_b, allow=False), {"description": "No pets"})
    projected = await features(pipeline, a.canonical_listing_id)
    assert projected[0]["status"] == "conflict" and projected[0]["typed_value"] is None
    assert len(projected[0]["supporting_fact_ids"]) == 2


async def test_new_sanitized_hash_with_unchanged_legacy_fingerprint_supersedes_old_job(pipeline):
    service, sessions = pipeline
    source = await seed(pipeline)
    await service.observe(source)
    old = await service.claim()
    changed = SourceInput.model_validate(source.model_dump() | {"content_hash": digest({"description": "No pets"})})
    await service.observe(changed)
    assert (await service.complete(old, fake_extract(old), {"description": "Pets allowed"})).status == "superseded"
    new = await service.claim()
    assert new.generation == old.generation + 1
    await service.complete(new, fake_extract(new, allow=False), {"description": "No pets"})
    async with sessions() as session:
        assert (await session.get(AiFactSource, source.source_record_id)).generation == 2
    assert await count(pipeline, AiListingFact) == 1


@pytest.mark.parametrize("change", ["fingerprint", "retire", "delete", "remap", "hide", "listing_delete",
                                    "raw_payload", "normalized_payload", "source_price"])
async def test_real_authority_change_rejects_stale_worker_before_ingest(pipeline, change):
    service, sessions = pipeline
    source = await seed(pipeline)
    await service.observe(source)
    claim = await service.claim()
    async with sessions() as session, session.begin():
        if change == "fingerprint":
            await session.execute(text("UPDATE external_listing_sources SET fingerprint=:hash"), {"hash": "b" * 64})
        elif change == "retire":
            await session.execute(text("UPDATE external_listing_sources SET current_status='removed'"))
        elif change == "delete":
            await session.execute(text("DELETE FROM external_listing_sources"))
        elif change == "remap":
            await session.execute(text("UPDATE external_listing_sources SET canonical_listing_id=:id"), {"id": uuid4()})
        elif change == "hide":
            await session.execute(text("UPDATE listings SET status='hidden'"))
        elif change == "raw_payload":
            await session.execute(text("UPDATE external_listing_sources SET raw_payload='{}'::jsonb || jsonb_build_object('changed',true)"))
        elif change == "normalized_payload":
            await session.execute(text("UPDATE external_listing_sources SET normalized_payload='{}'::jsonb || jsonb_build_object('changed',true)"))
        elif change == "source_price":
            await session.execute(text("UPDATE external_listing_sources SET source_price_text='changed synthetic price'"))
        else:
            await session.execute(text("DELETE FROM listings"))
    result = await service.complete(claim, fake_extract(claim), {"description": "Pets allowed"})
    assert result.status == "superseded"
    assert await count(pipeline, AiListingFact) == 0
    assert await features(pipeline, source.canonical_listing_id) == []


async def test_retirement_preserves_history_and_other_source_support(pipeline):
    service, sessions = pipeline
    a = await seed(pipeline)
    b = await seed(pipeline, listing_id=a.canonical_listing_id)
    for item in (a, b):
        await service.observe(item)
        claim = await service.claim()
        await service.complete(claim, fake_extract(claim), {"description": "Pets allowed"})
    async with sessions() as session, session.begin():
        await session.execute(text("UPDATE external_listing_sources SET current_status='removed' WHERE id=:id"),
                              {"id": a.source_record_id})
    await service.reconcile_listing(a.canonical_listing_id)
    assert (await features(pipeline, a.canonical_listing_id))[0]["status"] == "explicit_allow"
    async with sessions() as session, session.begin():
        await session.execute(text("DELETE FROM external_listing_sources"))
    await service.reconcile_listing(a.canonical_listing_id)
    assert await features(pipeline, a.canonical_listing_id) == []
    assert await count(pipeline, AiListingFact) == 2


async def test_expired_claim_recovery_increments_fence_and_rejects_old_worker(pipeline):
    service, sessions = pipeline
    await service.observe(await seed(pipeline))
    old = await service.claim()
    async with sessions() as session, session.begin():
        await session.execute(text("UPDATE ai_fact_jobs SET lease_until=clock_timestamp()-interval '1 second'"))
    new = await service.claim()
    assert new.job_id == old.job_id and new.fence == old.fence + 1
    with pytest.raises(StaleFactWorker):
        await service.complete(old, fake_extract(old), {"description": "Pets allowed"})
    await service.complete(new, fake_extract(new), {"description": "Pets allowed"})
    assert await count(pipeline, AiListingFact) == 1


async def test_error_retry_delay_and_exhausted_attempts_are_durable(pipeline):
    service, sessions = pipeline
    await service.observe(await seed(pipeline))
    first = await service.claim()
    assert (await service.fail(first, retryable=True, code="EXTRACTOR_FAILED")).status == "pending"
    assert await service.claim() is None
    async with sessions() as session, session.begin():
        await session.execute(text("UPDATE ai_fact_jobs SET available_at=clock_timestamp()-interval '1 second'"))
    second = await service.claim()
    assert second.fence == first.fence + 1
    assert (await service.fail(second, retryable=True, code="INVALID_RESULT")).status == "failed"
    assert await service.claim() is None


async def test_projection_outbox_failure_rolls_back_facts_source_and_job(pipeline):
    service, sessions = pipeline
    source = await seed(pipeline)
    await service.observe(source)
    claim = await service.claim()
    async with sessions() as session, session.begin():
        await session.execute(text("CREATE FUNCTION fail_rematch() RETURNS trigger LANGUAGE plpgsql AS $$ "
                                   "BEGIN RAISE EXCEPTION 'synthetic rematch storage failure'; END $$"))
        await session.execute(text("CREATE TRIGGER fail_rematch BEFORE INSERT ON ai_fact_rematch_events "
                                   "FOR EACH ROW EXECUTE FUNCTION fail_rematch()"))
    with pytest.raises(DBAPIError):
        await service.complete(claim, fake_extract(claim), {"description": "Pets allowed"})
    assert await count(pipeline, AiListingFact) == 0
    assert await count(pipeline, AiListingFactBatch) == 0
    assert await count(pipeline, AiFactRematchEvent) == 1
    async with sessions() as session:
        assert (await session.get(AiFactSource, source.source_record_id)).batch_id is None
        assert (await session.get(AiFactJob, claim.job_id)).status == "running"


async def test_late_lease_rollback_uses_db_deadline_even_with_forged_claim_deadline(pipeline):
    service, sessions = pipeline
    short = FactPipeline(sessions, FactQueuePolicy(lease_seconds=1, max_attempts=2, retry_delay_seconds=1),
                         service.vocabulary, resolver_version=service.resolver_version)
    await short.observe(await seed(pipeline))
    claim = await short.claim()
    # Simulate a slow write after the initial valid lease check.
    async with sessions() as session, session.begin():
        await session.execute(text("CREATE FUNCTION slow_rematch() RETURNS trigger LANGUAGE plpgsql AS $$ "
                                   "BEGIN PERFORM pg_sleep(1.2); RETURN NEW; END $$"))
        await session.execute(text("CREATE TRIGGER slow_rematch BEFORE INSERT ON ai_fact_rematch_events "
                                   "FOR EACH ROW EXECUTE FUNCTION slow_rematch()"))
    forged = claim.model_copy(update={"lease_until": datetime(2099, 1, 1, tzinfo=UTC)})
    with pytest.raises(StaleFactWorker, match="during publication"):
        await short.complete(forged, fake_extract(claim), {"description": "Pets allowed"})
    assert await count(pipeline, AiListingFact) == 0
    assert await count(pipeline, AiFactRematchEvent) == 1


async def test_reconcile_repairs_missing_job_without_duplicate_revision_and_supports_cursor(pipeline):
    service, sessions = pipeline
    source = await seed(pipeline)
    job = await service.observe(source)
    async with sessions() as session, session.begin():
        await session.execute(text("DELETE FROM ai_fact_jobs WHERE id=:id"), {"id": job})
    assert await service.reconcile(limit=1) == [source.canonical_listing_id]
    assert await service.reconcile(limit=1, after=source.canonical_listing_id) == []
    assert await count(pipeline, AiFactJob) == 1
    assert await count(pipeline, AiFactRematchEvent) == 1


async def test_source_canonical_remap_is_not_implicitly_adopted(pipeline):
    service, sessions = pipeline
    source = await seed(pipeline)
    await service.observe(source)
    other = uuid4()
    async with sessions() as session, session.begin():
        await session.execute(text("INSERT INTO listings(id,status) VALUES (:id,'published')"), {"id": other})
        await session.execute(text("UPDATE external_listing_sources SET canonical_listing_id=:id"), {"id": other})
    moved = SourceInput.model_validate(source.model_dump() | {"canonical_listing_id": other})
    with pytest.raises(SourceIdentityConflict):
        await service.observe(moved)
    await service.reconcile_listing(source.canonical_listing_id)
    assert await features(pipeline, source.canonical_listing_id) == []


async def test_resolver_version_change_emits_one_new_revision(pipeline):
    service, sessions = pipeline
    source = await seed(pipeline)
    await service.observe(source)
    claim = await service.claim()
    await service.complete(claim, fake_extract(claim), {"description": "Pets allowed"})
    old_count = await count(pipeline, AiFactRematchEvent)
    next_version = FactPipeline(sessions, service.policy, service.vocabulary, resolver_version="source-resolver.test.v2")
    revision = await next_version.reconcile_listing(source.canonical_listing_id)
    assert await next_version.reconcile_listing(source.canonical_listing_id) == revision
    assert await count(pipeline, AiFactRematchEvent) == old_count + 1
    assert await count(pipeline, AiFactCatalog) == 1


async def test_invalid_hash_scope_and_generation_do_not_commit(pipeline):
    service, _ = pipeline
    await service.observe(await seed(pipeline))
    claim = await service.claim()
    batch = fake_extract(claim)
    with pytest.raises(ValueError, match="hash mismatch"):
        await service.complete(claim, batch, {"description": "No pets"})
    changed = batch.model_dump() | {"source_generation": claim.generation + 1}
    with pytest.raises(ValueError, match="claimed input"):
        await service.complete(claim, FactBatch.model_validate(changed), {"description": "Pets allowed"})
    assert await count(pipeline, AiListingFact) == 0


async def test_observe_complete_race_cannot_resurrect_previous_generation(pipeline):
    service, sessions = pipeline
    source = await seed(pipeline)
    await service.observe(source)
    claim = await service.claim()
    changed = SourceInput.model_validate(source.model_dump() | {"content_hash": digest({"description": "No pets"})})
    await asyncio.gather(service.complete(claim, fake_extract(claim), {"description": "Pets allowed"}),
                         service.observe(changed))
    assert await features(pipeline, source.canonical_listing_id) == []
    async with sessions() as session:
        assert (await session.get(AiFactSource, source.source_record_id)).generation == 2
    new = await service.claim()
    assert new.generation == 2


async def test_lock_wait_rechecks_database_clock_before_any_facts_write(pipeline):
    service, sessions = pipeline
    await service.observe(await seed(pipeline))
    claim = await service.claim()
    async with sessions() as blocker, blocker.begin():
        await blocker.get(AiFactJob, claim.job_id, with_for_update=True)
        task = asyncio.create_task(service.complete(claim, fake_extract(claim), {"description": "Pets allowed"}))
        await asyncio.sleep(0.1)
        await blocker.execute(text("UPDATE ai_fact_jobs SET lease_until=clock_timestamp()-interval '1 second'"))
    with pytest.raises(StaleFactWorker):
        await task
    assert await count(pipeline, AiListingFact) == 0


async def test_check_only_refresh_does_not_change_generation_or_content_age(pipeline):
    service, sessions = pipeline
    source = await seed(pipeline)
    job = await service.observe(source)
    claim = await service.claim()
    await service.complete(claim, fake_extract(claim), {"description": "Pets allowed"})
    count_before = await count(pipeline, AiFactRematchEvent)
    async with sessions() as session, session.begin():
        old = await session.get(AiListingFactBatch, claim.job_id)
        old_change = old.last_content_change_at
        await session.execute(text("UPDATE external_listing_sources SET last_success_at=clock_timestamp()"))
    assert await service.observe(source) == job
    assert await count(pipeline, AiFactRematchEvent) == count_before
    async with sessions() as session:
        assert (await session.get(AiFactSource, source.source_record_id)).generation == 1
        assert (await session.get(AiListingFactBatch, claim.job_id)).last_content_change_at == old_change


async def test_reconcile_cancels_pending_job_for_retired_source(pipeline):
    service, sessions = pipeline
    source = await seed(pipeline)
    await service.observe(source)
    async with sessions() as session, session.begin():
        await session.execute(text("UPDATE external_listing_sources SET current_status='removed'"))
    await service.reconcile_listing(source.canonical_listing_id)
    assert await service.claim() is None
    async with sessions() as session:
        assert (await session.scalar(select(AiFactJob))).status == "superseded"


async def test_corrupt_current_batch_invalidates_projection_instead_of_wide_fallback(pipeline):
    service, sessions = pipeline
    source = await seed(pipeline)
    await service.observe(source)
    claim = await service.claim()
    await service.complete(claim, fake_extract(claim), {"description": "Pets allowed"})
    async with sessions() as session, session.begin():
        await session.execute(update(AiListingFact).values(qualifiers={"unrecognized": True}))
    await service.reconcile_listing(source.canonical_listing_id)
    assert await features(pipeline, source.canonical_listing_id) == []


async def test_existing_projection_revision_is_never_decreased(pipeline):
    service, sessions = pipeline
    source = await seed(pipeline)
    async with sessions() as session, session.begin():
        session.add(AiListingSearchFeatures(canonical_listing_id=source.canonical_listing_id, feature_revision=7,
                                            schema_version="ai-facts.v1", taxonomy_version="ai-search.v1",
                                            resolver_version="previous.v1", input_hash="c" * 64,
                                            computed_at=datetime.now(UTC), features=[]))
    await service.observe(source)
    async with sessions() as session:
        assert (await session.get(AiListingSearchFeatures, source.canonical_listing_id)).feature_revision == 8


async def test_crash_reclaims_are_bounded_and_old_failure_cannot_reset_new_lease(pipeline):
    service, sessions = pipeline
    await service.observe(await seed(pipeline))
    first = await service.claim()
    async with sessions() as session, session.begin():
        await session.execute(text("UPDATE ai_fact_jobs SET lease_until=clock_timestamp()-interval '1 second'"))
    second = await service.claim()
    with pytest.raises(StaleFactWorker):
        await service.fail(first, retryable=True, code="EXTRACTOR_FAILED")
    async with sessions() as session, session.begin():
        await session.execute(text("UPDATE ai_fact_jobs SET lease_until=clock_timestamp()-interval '1 second'"))
    assert await service.claim() is None
    async with sessions() as session:
        job = await session.get(AiFactJob, second.job_id)
        assert job.status == "failed" and job.failure_code == "ATTEMPTS_EXHAUSTED"


async def test_invalid_vocabulary_input_is_rejected_before_persistence(pipeline):
    service, _ = pipeline
    await service.observe(await seed(pipeline))
    claim = await service.claim()
    data = fake_extract(claim).model_dump()
    data["facts"][0].update(key="amenity", status="explicit_allow", typed_value={"kind": "boolean", "value": True},
                             qualifiers={"amenity_code": "unapproved"})
    with pytest.raises(ValueError, match="unsupported amenity"):
        await service.complete(claim, FactBatch.model_validate(data), {"description": "Pets allowed"})
    assert await count(pipeline, AiListingFact) == 0


async def test_queue_downgrade_preserves_jobs_and_events(pipeline):
    service, sessions = pipeline
    await service.observe(await seed(pipeline))
    # The actual migration downgrade intentionally performs no DROP or DELETE.
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    spec = importlib.util.spec_from_file_location("queue_downgrade", Path(__file__).parents[2] / "alembic/versions/0070_ai_fact_pipeline.py")
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    async with sessions() as session, session.begin():
        connection = await session.connection()

        def downgrade(sync):
            with Operations.context(MigrationContext.configure(sync)):
                migration.downgrade()

        await connection.run_sync(downgrade)
    assert await count(pipeline, AiFactJob) == 1
    assert await count(pipeline, AiFactRematchEvent) == 1


async def test_snapshot_change_between_input_preparation_and_enqueue_is_rejected(pipeline):
    service, sessions = pipeline
    source = await seed(pipeline)
    async with sessions() as session, session.begin():
        await session.execute(text("UPDATE external_listing_sources SET normalized_payload=jsonb_build_object('changed',true)"))
    with pytest.raises(SourceIdentityConflict, match="before observe"):
        await service.observe(source)
    assert await count(pipeline, AiFactSource) == 0
    assert await count(pipeline, AiFactJob) == 0


async def test_payload_mutation_after_success_invalidates_projection_without_fingerprint_update(pipeline):
    service, sessions = pipeline
    source = await seed(pipeline)
    await service.observe(source)
    claim = await service.claim()
    await service.complete(claim, fake_extract(claim), {"description": "Pets allowed"})
    async with sessions() as session, session.begin():
        await session.execute(text("UPDATE external_listing_sources SET normalized_payload=jsonb_build_object('changed',true)"))
    await service.reconcile_listing(source.canonical_listing_id)
    assert await features(pipeline, source.canonical_listing_id) == []
