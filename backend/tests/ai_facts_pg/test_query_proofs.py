"""Real SQL invalidation on synthetic stored sources; no application DB."""
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, literal, select, text
from test_current_projection import completed
from test_fact_pipeline import seed
from typed_match_cases import VOCABULARY, intent

from app.models import Listing
from app.models.ai_listing_facts import AiListingSearchFeatures
from app.repositories.ai_hard_matching import hard_match_predicate
from app.repositories.ai_query_proofs import QueryProofs, current_projection_predicate, projection_signature
from app.services.ai_hard_matching import compile_hard_match

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def proofs(pipeline):
    service, sessions = pipeline
    async with sessions() as session, session.begin():
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
