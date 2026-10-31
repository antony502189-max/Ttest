"""Write-token dependency tests on real PostgreSQL, including old snapshots."""
import asyncio
import json
from uuid import uuid4

import pytest
from sqlalchemy import event, func, literal, select, text
from test_current_projection import completed
from test_query_proofs import guard
from test_query_proofs import proofs as proof_fixture

from app.models import Listing
from app.repositories import ai_query_proofs
from app.repositories.ai_query_proofs import current_projection_predicate

pytestmark = pytest.mark.integration
proofs = proof_fixture


async def signature(session, listing):
    return await session.scalar(select(func.ai_live_input_signature(literal(listing))))


async def test_fast_path_never_executes_full_digest_but_old_proofs_still_do(pipeline, proofs, monkeypatch):
    _, sessions = pipeline
    source = await completed(pipeline)
    assert await proofs.prepare(source.canonical_listing_id)
    async with sessions() as s, s.begin():
        await s.execute(text("CREATE FUNCTION forbidden_digest(uuid) RETURNS text LANGUAGE plpgsql AS $$ "
                             "BEGIN RAISE EXCEPTION 'full digest executed'; END $$"))
    monkeypatch.setattr(ai_query_proofs, "projection_signature", lambda lid: func.forbidden_digest(lid))
    assert await guard(proofs, source.canonical_listing_id)
    async with sessions() as s, s.begin():
        await s.execute(text("UPDATE ai_query_proofs SET input_signature=NULL, input_binding=NULL, input_vector=NULL"))
    with pytest.raises(Exception, match="full digest executed"):
        await guard(proofs, source.canonical_listing_id)
    monkeypatch.undo()
    assert await guard(proofs, source.canonical_listing_id)
    # Legacy proof is upgraded only through the real verifier/CAS.
    assert await proofs.prepare(source.canonical_listing_id)
    assert await guard(proofs, source.canonical_listing_id)


@pytest.mark.parametrize("damage", ["listing", "external", "batch", "epoch"])
async def test_missing_tokens_fail_closed_and_do_not_fall_back(pipeline, proofs, damage):
    _, sessions = pipeline
    source = await completed(pipeline)
    assert await proofs.prepare(source.canonical_listing_id)
    async with sessions() as s, s.begin():
        if damage == "epoch":
            await s.execute(text("DELETE FROM ai_live_input_epochs"))
        else:
            await s.execute(text("DELETE FROM ai_live_input_versions WHERE kind=:kind"), {"kind": damage})
        assert await signature(s, source.canonical_listing_id) is None
    assert not await guard(proofs, source.canonical_listing_id)
    assert not await proofs.prepare(source.canonical_listing_id)


@pytest.mark.parametrize("change", ["signature", "resolver_version", "vocabulary_hash", "feature_revision", "input_signature", "input_vector"])
async def test_fast_binding_rejects_tampered_proof_fields(pipeline, proofs, change):
    service, sessions = pipeline
    source = await completed(pipeline)
    assert await proofs.prepare(source.canonical_listing_id)
    value = "feature_revision+1" if change == "feature_revision" else "'other.v1'" if change == "resolver_version" else "repeat('f',64)"
    if change == "input_vector":
        value = "jsonb_build_object('broken',true)"
    async with sessions() as s, s.begin():
        await s.execute(text(f"UPDATE ai_query_proofs SET {change}={value}"))
    assert not await guard(proofs, source.canonical_listing_id)
    if change in {"resolver_version", "vocabulary_hash"}:
        async with sessions() as s:
            assert not await s.scalar(select(current_projection_predicate(literal(source.canonical_listing_id),
                resolver_version="other.v1" if change == "resolver_version" else service.resolver_version,
                vocabulary_hash="f"*64 if change == "vocabulary_hash" else service.vocabulary_hash)))


async def test_restore_noops_rollback_and_independent_concurrent_writers(pipeline, proofs):
    _, sessions = pipeline
    sources = [await completed(pipeline) for _ in range(8)]
    for source in sources:
        assert await proofs.prepare(source.canonical_listing_id)
    first = sources[0]
    async with sessions() as s:
        before = await signature(s, first.canonical_listing_id)
        await s.execute(text("UPDATE external_listing_sources SET source_url=source_url"))
        assert await signature(s, first.canonical_listing_id) == before
        await s.execute(text("UPDATE external_listing_sources SET source_url='https://example.invalid/temporary' WHERE id=:id"),
                        {"id": first.source_record_id})
        assert await signature(s, first.canonical_listing_id) != before
        await s.rollback()
        assert await signature(s, first.canonical_listing_id) == before
    async def write(source):
        async with sessions() as s, s.begin():
            await s.execute(text("UPDATE external_listing_sources SET source_url='https://example.invalid/changed' WHERE id=:id"),
                            {"id": source.source_record_id})
    await asyncio.gather(*(write(source) for source in sources))
    for source in sources:
        assert not await guard(proofs, source.canonical_listing_id)
    async with sessions() as s, s.begin():
        await s.execute(text("UPDATE external_listing_sources SET source_url='https://example.invalid/fixture' WHERE id=:id"),
                        {"id": first.source_record_id})
        # Restoring old values cannot accidentally reuse a formerly captured token.
        assert await signature(s, first.canonical_listing_id) != before
    # Equality with the originally verified v2 data is still allowed, but now
    # requires the original full live check until explicit re-preparation.
    assert await guard(proofs, first.canonical_listing_id)


async def test_old_rr_writer_updates_batch_token_after_relationship_changes(pipeline, proofs):
    _, sessions = pipeline
    first, second = await completed(pipeline), await completed(pipeline)
    async with sessions() as old_writer, old_writer.begin():
        await old_writer.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        before = await signature(old_writer, second.canonical_listing_id)
        async with sessions() as writer, writer.begin():
            await writer.execute(text("UPDATE ai_fact_sources SET batch_id=(SELECT batch_id FROM ai_fact_sources "
                                     "WHERE source_record_id=:first) WHERE source_record_id=:second"),
                                 {"first": first.source_record_id, "second": second.source_record_id})
        # The writer's snapshot cannot see the new association. It must still
        # invalidate its batch token without deriving affected canonical IDs.
        await old_writer.execute(text("UPDATE ai_listing_facts SET evidence=jsonb_build_array(jsonb_build_object('bad',true)) WHERE batch_id="
                                      "(SELECT batch_id FROM ai_fact_sources WHERE source_record_id=:id)"),
                                 {"id": first.source_record_id})
        assert await signature(old_writer, second.canonical_listing_id) == before
    async with sessions() as s:
        after = await signature(s, second.canonical_listing_id)
        assert after != before
        token = await s.scalar(text("SELECT token FROM ai_live_input_versions WHERE kind='batch' AND record_id="
                                    "(SELECT batch_id FROM ai_fact_sources WHERE source_record_id=:id)"),
                               {"id": second.source_record_id})
        assert token is not None


async def test_batch_move_invalidates_both_former_and_new_dependencies(pipeline, proofs):
    _, sessions = pipeline
    first, second = await completed(pipeline), await completed(pipeline)
    for source in (first, second):
        assert await proofs.prepare(source.canonical_listing_id)
    async with sessions() as s, s.begin():
        await s.execute(text("UPDATE ai_listing_facts SET scope_hash=repeat('a',64), "
                             "batch_id=(SELECT batch_id FROM ai_fact_sources WHERE source_record_id=:b) "
                             "WHERE batch_id=(SELECT batch_id FROM ai_fact_sources WHERE source_record_id=:a)"),
                        {"a": first.source_record_id, "b": second.source_record_id})
    for source in (first, second):
        assert not await guard(proofs, source.canonical_listing_id)


@pytest.mark.parametrize("table", ["external_listing_sources", "ai_listing_facts", "ai_live_input_versions"])
async def test_truncate_epoch_never_revives_prepared_proof(pipeline, proofs, table):
    _, sessions = pipeline
    source = await completed(pipeline)
    assert await proofs.prepare(source.canonical_listing_id)
    async with sessions() as s, s.begin():
        before = await s.scalar(text("SELECT epoch FROM ai_live_input_epochs"))
        await s.execute(text(f"TRUNCATE {table} CASCADE"))
        assert await s.scalar(text("SELECT epoch FROM ai_live_input_epochs")) != before
    assert not await guard(proofs, source.canonical_listing_id)


async def test_input_versions_are_scoped_before_count_and_limit(pipeline, proofs):
    service, sessions = pipeline
    first, second = await completed(pipeline), await completed(pipeline)
    for source in (first, second):
        assert await proofs.prepare(source.canonical_listing_id)
    async with sessions() as s, s.begin():
        await s.execute(text("UPDATE external_listing_sources SET raw_payload=jsonb_build_object('changed',true) WHERE id=:id"),
                        {"id": first.source_record_id})
    query = select(Listing.id).where(current_projection_predicate(Listing.id,
        resolver_version=service.resolver_version, vocabulary_hash=service.vocabulary_hash))
    async with sessions() as s:
        assert await s.scalar(select(func.count()).select_from(query.subquery())) == 1
        assert (await s.scalars(query.order_by(Listing.id).limit(1))).all() == [second.canonical_listing_id]


async def test_bounded_full_digest_vs_token_plan(pipeline, proofs):
    service, sessions = pipeline
    sources = [await completed(pipeline) for _ in range(32)]
    for source in sources:
        assert await proofs.prepare(source.canonical_listing_id)
    query = select(func.count()).select_from(Listing).where(current_projection_predicate(Listing.id,
        resolver_version=service.resolver_version, vocabulary_hash=service.vocabulary_hash))
    async with sessions() as s, s.begin():
        # A small candidate set must not scan/hash unrelated version records.
        await s.execute(text("INSERT INTO ai_live_input_versions (kind,record_id) "
                             "SELECT 'listing',gen_random_uuid() FROM generate_series(1,4096)"))
        await s.execute(text("ANALYZE"))
        captured = []
        def capture(connection, cursor, statement, parameters, context, executemany):
            captured.append((statement, parameters))
        event.listen(s.bind.sync_engine, "before_cursor_execute", capture)
        try:
            assert await s.scalar(query) == 32
        finally:
            event.remove(s.bind.sync_engine, "before_cursor_execute", capture)
        sql, parameters = captured[-1]
        raw = await (await s.connection()).get_raw_connection()
        async def explain():
            result = await raw.driver_connection.fetchval("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql, *parameters)
            return json.loads(result) if isinstance(result, str) else result
        fast = await explain()
        await s.execute(text("UPDATE ai_query_proofs SET input_signature=NULL, input_binding=NULL, input_vector=NULL"))
        legacy = await explain()
        assert await s.scalar(query) == 32
        def nodes(node):
            yield node
            for child in node.get("Plans", []):
                yield from nodes(child)
        def full_fact_rows(plan):
            return sum(n["Actual Rows"] * n["Actual Loops"] for n in nodes(plan[0]["Plan"])
                       if n.get("Relation Name") == "ai_listing_facts")
        assert full_fact_rows(fast) == 0
        assert full_fact_rows(legacy) >= 32
        visits = [n for n in nodes(fast[0]["Plan"]) if n.get("Relation Name") == "ai_live_input_versions"
                  and n["Actual Loops"] > 0]
        assert visits and all(n["Node Type"] in {"Index Scan", "Index Only Scan"} for n in visits)
        assert sum(n["Actual Rows"] * n["Actual Loops"] for n in visits) == 32*3
        print("LIVE_INPUT_BOUNDED_PLAN=" + json.dumps({"listings": 32, "capacity_acceptance": False,
            "token": fast, "legacy": legacy}))


async def test_json_numeric_scale_is_not_a_noop_for_v2_serialization(pipeline, proofs):
    _, sessions = pipeline
    source = await completed(pipeline)
    async with sessions() as s, s.begin():
        await s.execute(text("ALTER TABLE listings ADD COLUMN numeric_fixture jsonb DEFAULT jsonb_build_object('n',1)"))
    assert await proofs.prepare(source.canonical_listing_id)
    async with sessions() as s, s.begin():
        before = await signature(s, source.canonical_listing_id)
        # JSONB equality is true, but canonical v2 serialization changes scale.
        assert await s.scalar(text("SELECT jsonb_build_object('n',1)=jsonb_build_object('n',1.0)"))
        await s.execute(text("UPDATE listings SET numeric_fixture=jsonb_build_object('n',1.0)"))
        assert await signature(s, source.canonical_listing_id) != before
    assert not await guard(proofs, source.canonical_listing_id)


async def test_copy_membership_and_noop_upsert_do_not_mix_listing_tokens(pipeline, proofs):
    _, sessions = pipeline
    first, second = await completed(pipeline), await completed(pipeline)
    for source in (first, second):
        assert await proofs.prepare(source.canonical_listing_id)
    async with sessions() as s, s.begin():
        before = await signature(s, first.canonical_listing_id)
        await s.execute(text("INSERT INTO external_listing_sources SELECT * FROM external_listing_sources WHERE id=:id "
                             "ON CONFLICT (id) DO UPDATE SET source_url=EXCLUDED.source_url"), {"id": first.source_record_id})
        assert await signature(s, first.canonical_listing_id) == before
        raw = await (await s.connection()).get_raw_connection()
        await raw.driver_connection.copy_records_to_table("external_listing_sources",
            columns=["id", "canonical_listing_id", "fingerprint", "current_status"],
            records=[(uuid4(), first.canonical_listing_id, "0"*64, "active") for _ in range(8)])
        assert await signature(s, first.canonical_listing_id) != before
    assert not await guard(proofs, first.canonical_listing_id)
    assert await guard(proofs, second.canonical_listing_id)


async def test_cancelled_transaction_restores_original_tokens(pipeline, proofs):
    _, sessions = pipeline
    source = await completed(pipeline)
    assert await proofs.prepare(source.canonical_listing_id)
    ready = asyncio.Event()
    async def write():
        async with sessions() as s, s.begin():
            await s.execute(text("UPDATE external_listing_sources SET raw_payload=jsonb_build_object('cancel',true)"))
            ready.set()
            await asyncio.Event().wait()
    task = asyncio.create_task(write())
    await asyncio.wait_for(ready.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await guard(proofs, source.canonical_listing_id)


async def test_schema_changes_and_trigger_disable_reenable_require_reverification(pipeline, proofs):
    _, sessions = pipeline
    source = await completed(pipeline)
    assert await proofs.prepare(source.canonical_listing_id)
    async with sessions() as s, s.begin():
        await s.execute(text("ALTER TABLE listings ADD COLUMN new_evidence text DEFAULT 'new value'"))
    assert not await guard(proofs, source.canonical_listing_id)
    assert await proofs.prepare(source.canonical_listing_id)
    assert await guard(proofs, source.canonical_listing_id)
    async with sessions() as s, s.begin():
        await s.execute(text("ALTER TABLE external_listing_sources DISABLE TRIGGER ai_live_external_listing_sources_update"))
    assert not await guard(proofs, source.canonical_listing_id)
    assert not await proofs.prepare(source.canonical_listing_id)
    async with sessions() as s, s.begin():
        await s.execute(text("UPDATE external_listing_sources SET raw_payload=jsonb_build_object('disabled',true)"))
        await s.execute(text("ALTER TABLE external_listing_sources ENABLE ALWAYS TRIGGER ai_live_external_listing_sources_update"))
    assert not await guard(proofs, source.canonical_listing_id)
    assert not await proofs.prepare(source.canonical_listing_id)


async def test_replica_session_cannot_bypass_input_invalidation(pipeline, proofs):
    _, sessions = pipeline
    source = await completed(pipeline)
    assert await proofs.prepare(source.canonical_listing_id)
    async with sessions() as s, s.begin():
        await s.execute(text("SET LOCAL session_replication_role=replica"))
        await s.execute(text("UPDATE external_listing_sources SET raw_payload=jsonb_build_object('replica',true)"))
    assert not await guard(proofs, source.canonical_listing_id)
