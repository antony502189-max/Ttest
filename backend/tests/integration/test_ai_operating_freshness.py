"""Real card/map filtering separates source check age from proof age."""
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import func, select, update
from test_ai_verified_cards import setup

from app.db.session import SessionLocal
from app.external_sources import IdealistaSource
from app.models import ExternalListingSource, Listing
from app.models.ai_operating_policy import AiProofAge
from app.models.ai_search_quota import AIUsageDay
from app.repositories.ai_query_proofs import QueryProofs
from app.repositories.ai_verified_cards import SourceCoverageUnavailable
from app.repositories.listings import search_public_cards
from app.schemas.listings import ListingCardSearchRequest, ListingMapRequest
from app.services.ai_fact_quality import FactQualityPolicy
from app.services.external_removal import new_report, reconcile_source

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("status,state", [(403, "blocked"), (429, "temporary_error"),
                                        (None, "temporary_error"), (200, "unknown")])
async def test_direct_probe_error_excludes_ai_cards_and_map_but_preserves_manual(status, state):
    query, subject, session_id, ids, _ = await setup("long")
    query.pipeline.operating_policy = FactQualityPolicy(price_max_age_seconds=86400,
        policy_max_age_seconds=86400, evidence_retention_seconds=604800)
    async with SessionLocal.begin() as session:
        await session.execute(update(Listing).values(is_external=True))
    for listing_id in ids:
        assert await QueryProofs(query.pipeline).prepare(listing_id)
    cards = ListingCardSearchRequest(limit=1)
    viewport = ListingMapRequest(west=-17, south=28, east=-16, north=29, zoom=14)
    assert (await query.search_owned(subject, session_id, 1, cards)).cards.total == 3
    assert len((await query.map_owned(subject, session_id, 1, viewport)).map.items) == 3

    # Exercise the actual HTTP status classifier and persistence path. All
    # source requests use MockTransport; no DNS/provider/real source traffic.
    class SyntheticProbe(IdealistaSource):
        name = "synthetic"

        def is_listing_url(self, url):
            return url in {f"https://example.invalid/{i}" for i in range(4)}

    source = SyntheticProbe()
    await source.client.aclose()
    reply = [status, "<div id=app></div>"]

    def response(request):
        if reply[0] is None:
            raise httpx.ReadTimeout("synthetic source timeout", request=request)
        return httpx.Response(reply[0], text=reply[1], request=request)

    source.client = httpx.AsyncClient(transport=httpx.MockTransport(response))
    try:
        async with SessionLocal() as session:
            report = new_report()
            await reconcile_source(session, source, report=report)
            assert report[state] == 4
            rows = (await session.scalars(select(ExternalListingSource))).all()
            assert all(row.current_status == "active" and row.last_state_check_result == state for row in rows)
            assert (await search_public_cards(session, cards)).total == 4
        for listing_id in ids:
            await QueryProofs(query.pipeline).prepare(listing_id)
        assert (await query.search_owned(subject, session_id, 1, cards)).cards.total == 0
        assert not (await query.map_owned(subject, session_id, 1, viewport)).map.items
        current = (await query.sessions.get(subject, session_id)).intent
        with pytest.raises(SourceCoverageUnavailable):
            await query.query_candidate(subject, current, current.model_copy(update={"version": 2}), cards)
        async with SessionLocal() as session:
            assert await session.scalar(select(func.count()).select_from(AIUsageDay)) == 0
        reply[:] = [200, "<h1>Habitación individual en alquiler</h1><p>700 €/mes</p>"]
        async with SessionLocal() as session:
            report = new_report()
            await reconcile_source(session, source, report=report)
            assert report["active"] == 4
        for listing_id in ids:
            assert await QueryProofs(query.pipeline).prepare(listing_id)
        assert (await query.search_owned(subject, session_id, 1, cards)).cards.total == 3
        assert len((await query.map_owned(subject, session_id, 1, viewport)).map.items) == 3
        async with SessionLocal.begin() as session:
            await session.execute(update(ExternalListingSource).values(
                last_success_at=func.clock_timestamp() - timedelta(days=2)))
        # Repeated positive presence probes must not renew stale stored facts.
        async with SessionLocal() as session:
            report = new_report()
            await reconcile_source(session, source, report=report)
            assert report["active"] == 4
        for listing_id in ids:
            await QueryProofs(query.pipeline).prepare(listing_id)
        assert (await query.search_owned(subject, session_id, 1, cards)).cards.total == 0
        assert not (await query.map_owned(subject, session_id, 1, viewport)).map.items
        async with SessionLocal() as session:
            assert (await search_public_cards(session, cards)).total == 4
    finally:
        await source.close()


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
