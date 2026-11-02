"""Real card/map filtering separates source check age from proof age."""
from datetime import timedelta

import pytest
from sqlalchemy import func, update
from test_ai_verified_cards import setup

from app.db.session import SessionLocal
from app.models import ExternalListingSource
from app.models.ai_operating_policy import AiProofAge
from app.repositories.ai_query_proofs import QueryProofs
from app.repositories.ai_verified_cards import SourceCoverageUnavailable
from app.schemas.listings import ListingCardSearchRequest
from app.services.ai_fact_quality import FactQualityPolicy

pytestmark = pytest.mark.integration


async def test_source_age_and_signed_proof_age_independently_exclude_cards():
    query, subject, session_id, ids, _ = await setup("long")
    query.pipeline.operating_policy = FactQualityPolicy(price_max_age_seconds=86400,
        policy_max_age_seconds=86400, evidence_retention_seconds=604800)
    for listing_id in ids:
        assert await QueryProofs(query.pipeline).prepare(listing_id)
    payload = ListingCardSearchRequest()
    assert (await query.search_owned(subject, session_id, 1, payload)).cards.total == 3
    async with SessionLocal.begin() as conn:
        await conn.execute(update(ExternalListingSource).values(last_success_at=func.clock_timestamp() - timedelta(days=2)))
    # Rebuilding matching proofs does not invent a recent source check.
    for listing_id in ids:
        assert await QueryProofs(query.pipeline).prepare(listing_id)
    assert (await query.search_owned(subject, session_id, 1, payload)).cards.total == 0
    current = (await query.sessions.get(subject, session_id)).intent
    with pytest.raises(SourceCoverageUnavailable):
        await query.query_candidate(subject, current, current.model_copy(update={"version": 2}), payload)
    async with SessionLocal.begin() as conn:
        await conn.execute(update(ExternalListingSource).values(last_success_at=func.clock_timestamp()))
        await conn.execute(update(AiProofAge).values(prepared_at=func.clock_timestamp() - timedelta(days=2)))
    assert (await query.search_owned(subject, session_id, 1, payload)).cards.total == 0
    for listing_id in ids:
        assert await QueryProofs(query.pipeline).prepare(listing_id)
    assert (await query.search_owned(subject, session_id, 1, payload)).cards.total == 3
