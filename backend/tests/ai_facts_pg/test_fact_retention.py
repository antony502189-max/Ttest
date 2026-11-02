"""Real bounded evidence/cache deletion without legacy data mutations."""
from datetime import timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text, update
from test_current_projection import completed
from test_query_proofs import guard
from test_query_proofs import proofs as shared_proofs

from app.models.ai_fact_pipeline import AiFactCatalog, AiFactSource
from app.models.ai_listing_facts import AiListingFact, AiListingFactBatch
from app.models.ai_operating_policy import AiProofAge
from app.models.ai_query_proof import AiQueryProof
from app.repositories.ai_query_proofs import proof_age_predicate
from app.services.ai_fact_quality import FactQualityPolicy
from app.services.ai_fact_retention import AIFactRetention

proofs = shared_proofs
pytestmark = pytest.mark.integration

@pytest_asyncio.fixture(autouse=True)
async def operating_profile(pipeline, proofs):
    async with pipeline[1].begin() as conn:
        await (await conn.connection()).run_sync(AiProofAge.__table__.create)
    pipeline[0].operating_policy = FactQualityPolicy(price_max_age_seconds=86400,
        policy_max_age_seconds=86400, evidence_retention_seconds=604800)



async def test_proof_cache_expiry_is_not_source_freshness(pipeline, proofs):
    source = await completed(pipeline)
    assert await proofs.prepare(source.canonical_listing_id)
    _, sessions = pipeline
    async with sessions.begin() as conn:
        await conn.execute(update(AiProofAge).values(prepared_at=func.clock_timestamp() - timedelta(hours=24)))
    from sqlalchemy import literal
    async with sessions() as conn:
        assert not await conn.scalar(select(proof_age_predicate(literal(source.canonical_listing_id))))
    counts = await AIFactRetention(pipeline[0]).prune()
    assert counts["proofs"] == 1 and counts["sources"] == counts["batches"] == 0
    assert await proofs.prepare(source.canonical_listing_id)
    assert await guard(proofs, source.canonical_listing_id)


async def test_deleted_listing_removes_ai_copies_but_preserves_legacy_source(pipeline, proofs):
    source = await completed(pipeline)
    assert await proofs.prepare(source.canonical_listing_id)
    _, sessions = pipeline
    async with sessions.begin() as conn:
        await conn.execute(text("UPDATE listings SET deleted_at=clock_timestamp()"))
    counts = await AIFactRetention(pipeline[0]).prune()
    assert counts["sources"] == counts["facts"] == counts["batches"] == counts["catalogs"] == 1
    async with sessions() as conn:
        for model in (AiFactSource, AiListingFactBatch, AiListingFact, AiFactCatalog, AiQueryProof):
            assert await conn.scalar(select(func.count()).select_from(model)) == 0
        assert await conn.scalar(text("SELECT count(*) FROM external_listing_sources")) == 1
        assert await conn.scalar(text("SELECT count(*) FROM listings")) == 1


async def test_deleted_owner_invalidates_proof_and_removes_ai_of_still_published_listing(pipeline, proofs):
    source = await completed(pipeline)
    owner = uuid4()
    _, sessions = pipeline
    async with sessions.begin() as conn:
        await conn.execute(text("INSERT INTO users(id) VALUES (:owner)"), {"owner": owner})
        await conn.execute(text("UPDATE listings SET owner_user_id=:owner"), {"owner": owner})
    assert await proofs.prepare(source.canonical_listing_id)
    async with sessions.begin() as conn:
        await conn.execute(text("UPDATE users SET deleted_at=clock_timestamp()"))
    assert not await proofs.prepare(source.canonical_listing_id)
    counts = await AIFactRetention(pipeline[0]).prune()
    assert counts["sources"] == counts["facts"] == counts["catalogs"] == 1


async def test_old_unreferenced_evidence_is_deleted_but_current_batch_survives(pipeline, proofs):
    source = await completed(pipeline)
    assert await proofs.prepare(source.canonical_listing_id)
    _, sessions = pipeline
    async with sessions.begin() as conn:
        batch = await conn.scalar(select(AiListingFactBatch))
        fact = await conn.scalar(select(AiListingFact))
        batch_fields = {column.name: getattr(batch, column.name) for column in batch.__table__.columns}
        batch_fields.update(id=uuid4(), source_generation=batch.source_generation + 10,
            observed_at=batch.observed_at - timedelta(days=8))
        for field in ("last_successful_check_at", "last_content_change_at", "last_check_error_at"):
            if batch_fields[field] is not None:
                batch_fields[field] -= timedelta(days=8)
        conn.add(AiListingFactBatch(**batch_fields))
        await conn.flush()
        fact_fields = {column.name: getattr(fact, column.name) for column in fact.__table__.columns}
        fact_fields.update(id=uuid4(), batch_id=batch_fields["id"])
        conn.add(AiListingFact(**fact_fields))
    counts = await AIFactRetention(pipeline[0]).prune(batch_size=1)
    assert counts["facts"] == counts["batches"] == 1 and counts["sources"] == 0
    assert await guard(proofs, source.canonical_listing_id)
