from datetime import timedelta

import pytest
from sqlalchemy import func, literal, select, text
from test_current_projection import completed
from typed_match_cases import CASES, plan

from app.models import Listing
from app.models.ai_listing_facts import AiListingFact, AiListingFactBatch
from app.repositories.ai_fact_quality import audit_catalog, source_freshness_predicate
from app.services.ai_fact_quality import FactQualityPolicy

pytestmark = pytest.mark.integration
POLICY = FactQualityPolicy(price_max_age_seconds=60, policy_max_age_seconds=120, evidence_retention_seconds=1)
PLAN = plan(next(c for c in CASES if c["name"] == "pets"))


async def test_freshness_sql_before_count_and_limit_and_audit_reasons(pipeline):
    service, sessions = pipeline
    source = await completed(pipeline)
    async def audit():
        return await audit_catalog(service, eligibility=literal(True), plan=PLAN, policy=POLICY, limit=10)
    assert (await audit())["match"] == 1
    async with sessions() as session, session.begin():
        await session.execute(text("UPDATE external_listing_sources SET last_success_at=clock_timestamp()-interval '121 seconds'"))
    assert (await audit())["stale"] == 1
    async with sessions() as session:
        guard = source_freshness_predicate(Listing.id, PLAN, POLICY)
        assert await session.scalar(select(func.count()).select_from(Listing).where(guard)) == 0
        assert (await session.scalars(select(Listing.id).where(guard).limit(1))).all() == []
    async with sessions() as session, session.begin():
        await session.execute(text("UPDATE external_listing_sources SET last_success_at=clock_timestamp()+interval '1 day'"))
    assert (await audit())["stale"] == 1
    async with sessions() as session, session.begin():
        await session.execute(text("UPDATE external_listing_sources SET last_success_at=NULL"))
    assert (await audit())["unknown"] == 1
    async with sessions() as session, session.begin():
        await session.execute(text("UPDATE external_listing_sources SET current_status='unavailable'"))
    assert (await audit())["source_error"] == 1
    assert source.canonical_listing_id


async def test_retention_physically_deletes_evidence_and_rebuilds_pending_barrier(pipeline):
    service, sessions = pipeline
    source = await completed(pipeline)
    assert await service.purge_expired_evidence(source.canonical_listing_id, retention_seconds=300) == 0
    async with sessions() as session, session.begin():
        now = await session.scalar(select(func.clock_timestamp()))
        # Keep timestamp constraints satisfied while simulating elapsed time.
        await session.execute(text("UPDATE ai_listing_fact_batches SET observed_at=:old, "
                                   "last_successful_check_at=NULL,last_content_change_at=NULL,last_check_error_at=NULL"),
                              {"old": now - timedelta(days=1)})
    assert await service.purge_expired_evidence(source.canonical_listing_id, retention_seconds=1) == 1
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(AiListingFact)) == 0
        assert await session.scalar(select(func.count()).select_from(AiListingFactBatch)) == 0
    assert await service.read_current_projection(source.canonical_listing_id) is None
    assert await service.purge_expired_evidence(source.canonical_listing_id, retention_seconds=1) == 0
    # Identical source can be explicitly prepared again in a new generation.
    from test_fact_pipeline import fake_extract
    await service.observe(source)
    claim = await service.claim()
    assert claim.generation == 2
    await service.complete(claim, fake_extract(claim), {"description": "Pets allowed"})
    assert await service.read_current_projection(source.canonical_listing_id) is not None
