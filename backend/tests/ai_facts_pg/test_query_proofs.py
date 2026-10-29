"""Real SQL invalidation on synthetic stored sources; no application DB."""
import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import event, func, literal, or_, select, text
from sqlalchemy.sql import operators, visitors
from sqlalchemy.sql.elements import BinaryExpression
from sqlalchemy.sql.selectable import CompoundSelect
from test_current_projection import completed
from test_fact_pipeline import seed
from typed_match_cases import VOCABULARY, intent

from app.models import Listing
from app.models.ai_fact_pipeline import AiFactSource
from app.models.ai_listing_facts import AiListingSearchFeatures
from app.repositories.ai_hard_matching import hard_match_predicate
from app.repositories.ai_query_proofs import QueryProofs, current_projection_predicate, projection_signature
from app.services.ai_hard_matching import compile_hard_match

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def proofs(pipeline):
    service, sessions = pipeline
    async with sessions() as session, session.begin():
        # The proof now binds the one-to-one canonical room record too.
        from app.models.room_details import ListingRoomDetails
        columns = ", ".join(f'"{c.name}" {c.type.compile(dialect=session.bind.dialect)}'
                            for c in ListingRoomDetails.__table__.columns)
        await session.execute(text(f"CREATE TABLE listing_room_details ({columns})"))
        path = Path(__file__).parents[2] / "alembic/versions/0071_ai_query_proofs.py"
        spec = importlib.util.spec_from_file_location("query_proof_migration", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        def migrate(connection):
            with Operations.context(MigrationContext.configure(connection)):
                module.upgrade()
        await (await session.connection()).run_sync(migrate)
    return QueryProofs(service)


async def guard(proofs, listing_id):
    service = proofs.pipeline
    async with service.sessions() as session:
        return await session.scalar(select(current_projection_predicate(literal(listing_id),
            resolver_version=service.resolver_version, vocabulary_hash=service.vocabulary_hash)))


def legacy_signature(listing_id):
    """Keep the previous authority predicate as a v2 digest compatibility oracle."""
    replaced = []
    def restore_or(node):
        if not isinstance(node, BinaryExpression) or node.operator is not operators.in_op:
            return None
        if not isinstance(getattr(node.right, "element", None), CompoundSelect):
            return None
        external = node.left.table
        source = AiFactSource.__table__.alias()
        known = select(source.c.source_record_id).where(
            source.c.canonical_listing_id == listing_id).correlate_except(source)
        replaced.append(node)
        return or_(external.c.canonical_listing_id == listing_id, node.left.in_(known))
    signature = visitors.replacement_traverse(projection_signature(listing_id), {}, restore_or)
    assert len(replaced) == 1, "compatibility oracle must actually restore the old predicate"
    return signature


@pytest.mark.parametrize("change", ["none", "new_current", "remap", "delete", "remap_and_new", "over_bound"])
async def test_indexed_authority_preserves_existing_v2_digest_and_invalidation(pipeline, proofs, change):
    _, sessions = pipeline
    source = await completed(pipeline)
    lid = source.canonical_listing_id
    assert await proofs.prepare(lid)
    async with sessions() as session:
        assert await session.scalar(select(legacy_signature(literal(lid)))) == await session.scalar(
            select(projection_signature(literal(lid))))
    if change in {"remap", "remap_and_new", "delete"}:
        async with sessions() as session, session.begin():
            statement = ("DELETE FROM external_listing_sources WHERE id=:id" if change == "delete" else
                "UPDATE external_listing_sources SET canonical_listing_id=:new WHERE id=:id")
            await session.execute(text(statement), {"id": source.source_record_id, "new": uuid4()})
    if change in {"new_current", "remap_and_new"}:
        await seed(pipeline, listing_id=lid)
    if change == "over_bound":
        async with sessions() as session, session.begin():
            await session.execute(text("INSERT INTO external_listing_sources(id,canonical_listing_id,fingerprint,current_status) "
                "SELECT md5('extra:'||g::text)::uuid,:lid,repeat('a',64),'active' FROM generate_series(1,130) g"), {"lid":lid})
    async with sessions() as session:
        assert await session.scalar(select(legacy_signature(literal(lid)))) == await session.scalar(
            select(projection_signature(literal(lid))))
    assert await guard(proofs, lid) == (change == "none")


@pytest.mark.parametrize("correlated", [False, True])
async def test_authority_lookup_does_not_visit_unrelated_catalog_sources(pipeline, proofs, correlated):
    _, sessions = pipeline
    source = await completed(pipeline)
    async with sessions() as session, session.begin():
        # Same canonical-source index as the full legacy migration schema.
        await session.execute(text("CREATE INDEX test_source_canonical ON external_listing_sources(canonical_listing_id)"))
        await session.execute(text("INSERT INTO external_listing_sources(id,canonical_listing_id,fingerprint,current_status) "
            "SELECT md5('unrelated:'||g::text)::uuid,md5('other:'||g::text)::uuid,repeat('a',64),'active' "
            "FROM generate_series(1,2048) g"))
        await session.execute(text("ANALYZE external_listing_sources"))
        await session.execute(text("ANALYZE ai_fact_sources"))
        captured = []
        def capture(connection, cursor, statement, parameters, context, executemany):
            captured.append((statement, parameters))
        event.listen(session.bind.sync_engine, "before_cursor_execute", capture)
        try:
            statement = (select(projection_signature(Listing.id)).select_from(Listing).where(
                Listing.id == source.canonical_listing_id) if correlated else
                select(projection_signature(literal(source.canonical_listing_id))))
            await session.scalar(statement)
        finally:
            event.remove(session.bind.sync_engine, "before_cursor_execute", capture)
        statement, parameters = captured[0]
        raw = await (await session.connection()).get_raw_connection()
        plan = await raw.driver_connection.fetchval("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + statement, *parameters)
        if isinstance(plan, str):
            plan = json.loads(plan)
        def scans(node):
            own = [node] if node.get("Relation Name") == "external_listing_sources" else []
            return own + [item for child in node.get("Plans", []) for item in scans(child)]
        authority_scans = scans(plan[0]["Plan"])
        assert authority_scans
        assert all(node["Actual Rows"] + node.get("Rows Removed by Filter", 0) <= 1 for node in authority_scans)


async def test_correlated_proofs_keep_each_listing_scoped_after_source_remap(pipeline, proofs):
    service, sessions = pipeline
    first = await completed(pipeline)
    second = await completed(pipeline)
    ids = [first.canonical_listing_id, second.canonical_listing_id]
    for lid in ids:
        assert await proofs.prepare(lid)
    async def read():
        async with sessions() as session:
            return (await session.execute(select(Listing.id,
                projection_signature(Listing.id), legacy_signature(Listing.id),
                current_projection_predicate(Listing.id, resolver_version=service.resolver_version,
                    vocabulary_hash=service.vocabulary_hash)).where(Listing.id.in_(ids)))).all()
    before = {row[0]: row[1:] for row in await read()}
    assert all(new == old and valid for new, old, valid in before.values())
    async with sessions() as session, session.begin():
        await session.execute(text("UPDATE external_listing_sources SET canonical_listing_id=:target WHERE id=:source"),
            {"target": ids[1], "source": first.source_record_id})
    after = {row[0]: row[1:] for row in await read()}
    # Both the former owner and new owner must observe the remap. Each retains
    # its own digest, and the old proof cannot authorize either listing.
    assert all(new == old and not valid and new != before[lid][0]
               for lid, (new, old, valid) in after.items())
    assert after[ids[0]][0] != after[ids[1]][0]


async def test_only_verified_projection_can_be_certified(pipeline, proofs):
    service, sessions = pipeline
    source = await completed(pipeline)
    assert not await guard(proofs, source.canonical_listing_id)
    assert await proofs.prepare(source.canonical_listing_id)
    assert await guard(proofs, source.canonical_listing_id)
    assert await proofs.prepare(source.canonical_listing_id)
    assert not await proofs.prepare(uuid4())
    # Same digest across session time zones, including all stored timestamps.
    async with sessions() as session, session.begin():
        signature = await session.scalar(select(projection_signature(literal(source.canonical_listing_id))))
        await session.execute(text("SET LOCAL TIME ZONE 'Pacific/Auckland'"))
        assert await session.scalar(select(projection_signature(literal(source.canonical_listing_id)))) == signature
    async with sessions() as session:
        assert not await session.scalar(select(current_projection_predicate(literal(source.canonical_listing_id),
            resolver_version="different.v1", vocabulary_hash=service.vocabulary_hash)))
        assert not await session.scalar(select(current_projection_predicate(literal(source.canonical_listing_id),
            resolver_version=service.resolver_version, vocabulary_hash="b" * 64)))


@pytest.mark.parametrize("statement", [
    "UPDATE external_listing_sources SET raw_payload=jsonb_build_object('changed',true)",
    "UPDATE external_listing_sources SET normalized_payload=jsonb_build_object('changed',true)",
    "UPDATE external_listing_sources SET source_price_text='changed'",
    "UPDATE external_listing_sources SET source_url='https://example.invalid/changed'",
    "UPDATE external_listing_sources SET fingerprint=repeat('b',64)",
    "UPDATE external_listing_sources SET current_status='removed'",
    "UPDATE external_listing_sources SET canonical_listing_id=:new_id",
    "DELETE FROM external_listing_sources",
    "UPDATE listings SET status='hidden'",
    "UPDATE listings SET deleted_at=clock_timestamp()",
    "DELETE FROM listings",
    "DELETE FROM ai_listing_search_features",
    "UPDATE ai_fact_catalogs SET revision=revision+1",
    "UPDATE ai_listing_search_features SET features='[]'::jsonb",
    "UPDATE ai_listing_facts SET typed_value=jsonb_build_object('kind','policy','allowed',false)",
    "UPDATE ai_listing_facts SET evidence=jsonb_build_array(jsonb_build_object('bad',true))",
    "UPDATE ai_listing_fact_batches SET extractor_version='different.v1'",
    "UPDATE ai_fact_sources SET source_fingerprint=repeat('b',64)",
])
async def test_any_relevant_mutation_invalidates_existing_sql_proof(pipeline, proofs, statement):
    _, sessions = pipeline
    source = await completed(pipeline)
    assert await proofs.prepare(source.canonical_listing_id)
    async with sessions() as session, session.begin():
        await session.execute(text(statement), {"new_id": uuid4()})
    assert not await guard(proofs, source.canonical_listing_id)
    assert not await proofs.prepare(source.canonical_listing_id)


async def test_new_source_and_pending_generation_never_keep_old_proof(pipeline, proofs):
    service, _ = pipeline
    source = await completed(pipeline)
    assert await proofs.prepare(source.canonical_listing_id)
    await seed(pipeline, listing_id=source.canonical_listing_id)
    assert not await guard(proofs, source.canonical_listing_id)
    assert not await proofs.prepare(source.canonical_listing_id)
    # A second canonical listing is independent of the invalid first one.
    other = await completed(pipeline)
    assert await proofs.prepare(other.canonical_listing_id)
    await service.observe(other.model_copy(update={"extractor_version": "fake.v2"}))
    assert not await guard(proofs, other.canonical_listing_id)


@pytest.mark.parametrize("statement", [
    "UPDATE external_listing_sources SET raw_payload=jsonb_build_object('changed',true)",
    "UPDATE ai_listing_search_features SET features='[]'::jsonb",
    "UPDATE ai_listing_facts SET typed_value=jsonb_build_object('kind','policy','allowed',false)",
    "UPDATE ai_fact_catalogs SET revision=revision+1",
])
async def test_concurrent_change_after_snapshot_prevents_cas(pipeline, proofs, monkeypatch, statement):
    service, sessions = pipeline
    source = await completed(pipeline)
    original = service._read_current_projection
    async def changed(session, listing_id):
        result = await original(session, listing_id)
        # Reader sees its old RR snapshot; write transaction may commit freely.
        async with sessions() as writer, writer.begin():
            await writer.execute(text(statement))
        return result
    monkeypatch.setattr(service, "_read_current_projection", changed)
    assert not await proofs.prepare(source.canonical_listing_id)
    assert not await guard(proofs, source.canonical_listing_id)


async def test_correlated_guard_filters_real_projection_rows_before_count_and_limit(pipeline, proofs):
    _, sessions = pipeline
    first = await completed(pipeline)
    second = await completed(pipeline)
    assert await proofs.prepare(first.canonical_listing_id)
    assert await proofs.prepare(second.canonical_listing_id)
    async with sessions() as session, session.begin():
        await session.execute(text("UPDATE external_listing_sources SET current_status='removed' WHERE id=:id"),
                              {"id": first.source_record_id})
    service = proofs.pipeline
    compiled = compile_hard_match(intent({"pets": {"strength": "hard", "value": [
        {"species": "dog", "size": "small", "count": 1}]}}), VOCABULARY)
    query = select(Listing.id).join(AiListingSearchFeatures,
        AiListingSearchFeatures.canonical_listing_id == Listing.id).where(
        Listing.status == "published", Listing.deleted_at.is_(None),
        current_projection_predicate(Listing.id, resolver_version=service.resolver_version,
                                     vocabulary_hash=service.vocabulary_hash),
        hard_match_predicate(AiListingSearchFeatures.features, compiled))
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(query.subquery())) == 1
        assert (await session.scalars(query.order_by(Listing.id).limit(1))).all() == [second.canonical_listing_id]


async def test_read_only_verification_then_only_cache_write(pipeline, proofs, monkeypatch):
    service, sessions = pipeline
    source = await completed(pipeline)
    original = service._read_current_projection
    async def inspect(session, listing_id):
        assert await session.scalar(text("SHOW transaction_isolation")) == "repeatable read"
        assert await session.scalar(text("SHOW transaction_read_only")) == "on"
        return await original(session, listing_id)
    monkeypatch.setattr(service, "_read_current_projection", inspect)
    async with sessions() as session:
        before = await session.scalar(text("SELECT count(*) FROM ai_fact_rematch_events"))
    assert await proofs.prepare(source.canonical_listing_id)
    async with sessions() as session:
        assert await session.scalar(text("SELECT count(*) FROM ai_fact_rematch_events")) == before
        assert await session.scalar(text("SELECT count(*) FROM ai_query_proofs")) == 1


async def test_preparation_storage_failure_propagates(pipeline, proofs):
    from sqlalchemy.exc import DBAPIError
    _, sessions = pipeline
    source = await completed(pipeline)
    async with sessions() as session, session.begin():
        await session.execute(text("CREATE FUNCTION fail_proof() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
                                  "RAISE EXCEPTION 'synthetic_proof_failure'; END $$"))
        await session.execute(text("CREATE TRIGGER fail_proof BEFORE INSERT ON ai_query_proofs "
                                  "FOR EACH ROW EXECUTE FUNCTION fail_proof()"))
    with pytest.raises(DBAPIError):
        await proofs.prepare(source.canonical_listing_id)
    assert not await guard(proofs, source.canonical_listing_id)


@pytest.mark.parametrize("corruption", ["'[]'::jsonb", "jsonb_build_array(jsonb_build_object('bad',true))"])
async def test_projection_repair_after_corruption(pipeline, proofs, corruption):
    service, sessions = pipeline
    source = await completed(pipeline)
    assert await proofs.prepare(source.canonical_listing_id)
    original = await service.read_current_projection(source.canonical_listing_id)
    async with sessions() as session, session.begin():
        await session.execute(text(f"UPDATE ai_listing_search_features SET features={corruption}"))
    assert not await proofs.prepare(source.canonical_listing_id)
    revision = await service.reconcile_listing(source.canonical_listing_id)
    assert revision > original.feature_revision
    restored = await service.read_current_projection(source.canonical_listing_id)
    assert restored.features == original.features
    assert restored.input_hash == original.input_hash
    assert await proofs.prepare(source.canonical_listing_id)
    assert await guard(proofs, source.canonical_listing_id)
    assert await service.reconcile_listing(source.canonical_listing_id) == revision


async def test_semantic_verifier_upgrade_invalidates_existing_proof(pipeline, proofs, monkeypatch):
    from app.repositories import ai_query_proofs
    source = await completed(pipeline)
    current = ai_query_proofs.PROOF_CONTRACT_VERSION
    monkeypatch.setattr(ai_query_proofs, "PROOF_CONTRACT_VERSION", "legacy-verifier.test.v1")
    assert await proofs.prepare(source.canonical_listing_id)
    assert await guard(proofs, source.canonical_listing_id)
    monkeypatch.setattr(ai_query_proofs, "PROOF_CONTRACT_VERSION", current)
    assert not await guard(proofs, source.canonical_listing_id)
    assert await proofs.prepare(source.canonical_listing_id)
    assert await guard(proofs, source.canonical_listing_id)
