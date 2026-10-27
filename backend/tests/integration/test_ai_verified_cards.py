"""Existing cards and eligibility through verified SQL, on real PostGIS schema."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text, update
from test_listing_gallery_cards import _seed_listing_with_gallery

from app.db.session import SessionLocal
from app.models import ExternalListingSource, User
from app.models.ai_search_quota import AIUsageDay
from app.models.ai_search_session import AISearchSession
from app.models.moderation import ListingPromotion, ListingRestriction
from app.repositories.ai_fact_pipeline import FactPipeline
from app.repositories.ai_query_proofs import QueryProofs
from app.repositories.ai_search_quota import QuotaLedger
from app.repositories.ai_search_sessions import IntentVocabulary, SearchSessions, SessionError, SessionPolicy
from app.repositories.ai_verified_cards import VerifiedCardSearch
from app.repositories.listings import search_public_cards
from app.schemas.ai_fact_pipeline import FactQueuePolicy, SourceInput
from app.schemas.ai_listing_facts import FactBatch, FactVocabulary, digest
from app.schemas.ai_search_quota import LeasePolicy, QuotaSubject
from app.schemas.listings import ListingCardSearchRequest
from app.services.ai_card_cursors import InvalidAICursor

pytestmark = pytest.mark.integration


async def setup(rental_mode):
    vocabulary = FactVocabulary(amenity_codes=frozenset(), catalog_other_codes=frozenset(),
                               tenant_group_codes=frozenset(), municipality_zones=frozenset())
    pipeline = FactPipeline(SessionLocal, FactQueuePolicy(lease_seconds=60, max_attempts=2, retry_delay_seconds=1),
                            vocabulary, resolver_version="test-cards.v1")
    ledger = QuotaLedger(SessionLocal, LeasePolicy(reservation_seconds=60, running_seconds=60, recovery_grace_seconds=30))
    sessions = SearchSessions(ledger, SessionPolicy(inactivity_seconds=600), IntentVocabulary(frozenset(), frozenset(), frozenset()))
    subject = QuotaSubject(kind="guest", id=uuid4())
    owned = await sessions.create(subject)
    async with SessionLocal() as session, session.begin():
        await session.execute(update(AISearchSession).where(AISearchSession.id == owned.intent.session_id).values(
            version=1, criteria={"pets": {"strength": "hard", "value": [
                {"species": "dog", "size": "small", "count": 1}]}}))
        owner = User(email="verified-cards@example.test", password_hash="unused", name="Synthetic Host", role="host",
                     initials="SH", email_verified=True)
        session.add(owner)
        await session.flush()
        listings = [await _seed_listing_with_gallery(session, owner, rental_mode, str(i)) for i in range(4)]
        now = datetime.now(UTC)
        for i in (0, 1):
            session.add(ListingPromotion(listing_id=listings[i].id, starts_at=now - timedelta(hours=1),
                ends_at=now + timedelta(days=1), boosted_at=now - timedelta(minutes=i), payment_managed=False))
        sources = []
        for i, listing in enumerate(listings):
            source = ExternalListingSource(source_name="synthetic", external_id=str(i),
                source_url=f"https://example.invalid/{i}", canonical_listing_id=listing.id,
                fingerprint=digest(str(i)), raw_payload={}, normalized_payload={}, current_status="active",
                last_success_at=now, content_updated_at=now)
            session.add(source)
            sources.append(source)
        await session.flush()
        ids, source_ids = [l.id for l in listings], [s.id for s in sources]
    for i, source_id in enumerate(source_ids):
        description = "Pets allowed" if i else "No pets"
        async with SessionLocal() as session:
            _, authority = await pipeline._authority(session, ids[i], lock=False)
        request = SourceInput(source_record_id=source_id, canonical_listing_id=ids[i],
            content_hash=digest({"description": description}), snapshot_hash=authority[source_id].snapshot_hash,
            schema_version="ai-facts.v1", taxonomy_version="ai-search.v1", extractor_version="test-cards.v1")
        await pipeline.observe(request)
        claim = await pipeline.claim()
        batch = FactBatch.model_validate({"schema_version": claim.schema_version, "taxonomy_version": claim.taxonomy_version,
            "batch_id": uuid4(), "canonical_listing_id": ids[i], "source_record_id": source_id,
            "source_generation": claim.generation, "content_hash": claim.content_hash, "extractor_version": claim.extractor_version,
            "observed_at": datetime.now(UTC), "source_status": "active", "last_successful_check_at": None,
            "last_content_change_at": None, "last_check_error_at": None,
            "facts": [{"fact_id": uuid4(), "key": "pets", "status": "explicit_allow" if i else "explicit_deny",
                "typed_value": {"kind": "policy", "allowed": bool(i)}, "qualifiers": {}, "origin": "source_text",
                "evidence": [{"field": "description", "quote": description, "start": 0, "end": len(description)}]}]})
        await pipeline.complete(claim, batch, {"description": description})
        assert await QueryProofs(pipeline).prepare(ids[i])
    query = VerifiedCardSearch(pipeline, sessions, signing_key=b"synthetic-cards-key-not-a-secret32")
    return query, subject, owned.intent.session_id, ids, source_ids


@pytest.mark.parametrize("rental_mode", ["long", "holiday"])
async def test_existing_cards_top_gallery_and_both_cursor_directions(rental_mode):
    query, subject, session_id, ids, _ = await setup(rental_mode)
    payload = ListingCardSearchRequest(rentalMode=rental_mode, sort="price_asc", limit=1)
    first = await query.search_owned(subject, session_id, 1, payload)
    assert first.cards.total == 3 and first.cards.items[0].id == str(ids[1])
    assert first.cards.items[0].promoted and len(first.cards.items[0].imageUrls) == 5
    assert first.cards.items[0].coverImageUrl == first.cards.items[0].imageUrls[0]
    assert first.reason_codes == ("pets",) and first.cards.nextCursor
    second = await query.search_owned(subject, session_id, 1, payload.model_copy(update={"cursor": first.cards.nextCursor}))
    assert second.cards.total == 3 and second.cards.items[0].id != first.cards.items[0].id
    back = await query.search_owned(subject, session_id, 1, payload.model_copy(update={"cursor": second.cards.previousCursor}))
    assert back.cards.items == first.cards.items
    async with SessionLocal() as session:
        manual = await search_public_cards(session, payload)
        assert manual.total == 4 and manual.items[0].id == str(ids[0])
        assert await session.scalar(select(func.count()).select_from(AIUsageDay)) == 0


async def test_owned_session_and_signed_cursor_bindings():
    query, subject, session_id, _, _ = await setup("long")
    payload = ListingCardSearchRequest(limit=1)
    first = await query.search_owned(subject, session_id, 1, payload)
    with pytest.raises(SessionError, match="SESSION_NOT_FOUND"):
        await query.search_owned(QuotaSubject(kind="guest", id=uuid4()), session_id, 1, payload)
    with pytest.raises(SessionError, match="SESSION_VERSION_CONFLICT"):
        await query.search_owned(subject, session_id, 0, payload)
    with pytest.raises(InvalidAICursor):
        await query.search_owned(subject, session_id, 1, payload.model_copy(update={"cursor": first.cards.nextCursor + "x"}))
    with pytest.raises(InvalidAICursor):
        await query.search_owned(subject, session_id, 1, payload.model_copy(update={"cursor": first.cards.nextCursor, "sort": "price_asc"}))
    async with SessionLocal() as session, session.begin():
        await session.execute(update(AISearchSession).where(AISearchSession.id == session_id).values(version=2))
    with pytest.raises(InvalidAICursor):
        await query.search_owned(subject, session_id, 2, payload.model_copy(update={"cursor": first.cards.nextCursor}))


async def test_current_sources_and_public_eligibility_are_rechecked_before_count():
    query, subject, session_id, ids, source_ids = await setup("long")
    async with SessionLocal() as session, session.begin():
        # No revision bump: the source SQL proof must independently invalidate.
        await session.execute(update(ExternalListingSource).where(ExternalListingSource.id == source_ids[1]).values(
            raw_payload={"changed": True}))
        session.add(ListingRestriction(listing_id=ids[2], reason="synthetic", starts_at=datetime.now(UTC) - timedelta(hours=1)))
    page = await query.search_owned(subject, session_id, 1, ListingCardSearchRequest(limit=1))
    assert page.cards.total == 1 and [item.id for item in page.cards.items] == [str(ids[3])]
    async with SessionLocal() as session, session.begin():
        await session.execute(update(User).values(blocked=True))
    page = await query.search_owned(subject, session_id, 1, ListingCardSearchRequest(limit=1))
    assert page.cards.total == 0 and not page.cards.items


async def test_expired_session_cannot_page_without_debit():
    query, subject, session_id, _, _ = await setup("long")
    async with SessionLocal() as session, session.begin():
        await session.execute(text("UPDATE ai_search_sessions SET expires_at=clock_timestamp()-interval '1 second'"))
    with pytest.raises(SessionError, match="SESSION_EXPIRED"):
        await query.search_owned(subject, session_id, 1, ListingCardSearchRequest())
