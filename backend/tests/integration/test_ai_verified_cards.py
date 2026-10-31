"""Existing cards and eligibility through verified SQL, on real PostGIS schema."""
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, text, update
from test_listing_gallery_cards import _seed_listing_with_gallery

from app.db.session import SessionLocal
from app.models import ExternalListingSource, Listing, User
from app.models.ai_query_proof import AiQueryProof
from app.models.ai_search_quota import AIUsageDay
from app.models.ai_search_session import AISearchSession
from app.models.moderation import ListingPromotion, ListingRestriction
from app.models.room_details import ListingRoomDetails
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


async def test_fact_catalog_generation_rejects_same_sum_changes_and_restoration():
    from app.models.ai_fact_pipeline import AiFactCatalog
    query, subject, session_id, _, _ = await setup("long")
    # Unrelated synthetic entries isolate cursor context from live proof edits.
    extra = [uuid4(), uuid4()]
    async with SessionLocal() as session, session.begin():
        session.add_all([AiFactCatalog(canonical_listing_id=extra[0], revision=1),
                         AiFactCatalog(canonical_listing_id=extra[1], revision=2)])
    payload = ListingCardSearchRequest(limit=1)
    first = await query.search_owned(subject, session_id, 1, payload)
    assert first.cards.nextCursor
    async with SessionLocal() as session, session.begin():
        await session.execute(text("UPDATE ai_fact_catalogs SET revision=3-revision WHERE canonical_listing_id IN (:a,:b)"),
                              {"a": extra[0], "b": extra[1]})
    with pytest.raises(InvalidAICursor):
        await query.search_owned(subject, session_id, 1, payload.model_copy(update={"cursor": first.cards.nextCursor}))
    async with SessionLocal() as session, session.begin():
        await session.execute(text("UPDATE ai_fact_catalogs SET revision=3-revision WHERE canonical_listing_id IN (:a,:b)"),
                              {"a": extra[0], "b": extra[1]})
    with pytest.raises(InvalidAICursor):
        await query.search_owned(subject, session_id, 1, payload.model_copy(update={"cursor": first.cards.nextCursor}))
    assert (await query.search_owned(subject, session_id, 1, payload)).cards.total == first.cards.total == 3


async def test_missing_fact_population_fails_closed_without_quota_debit():
    query, subject, session_id, _, _ = await setup("long")
    async with SessionLocal() as session, session.begin():
        await session.execute(text("DELETE FROM ai_fact_population"))
    with pytest.raises(RuntimeError, match="fact-catalog population state is missing"):
        await query.search_owned(subject, session_id, 1, ListingCardSearchRequest())
    async with SessionLocal() as session:
        assert await session.scalar(select(func.count()).select_from(AIUsageDay)) == 0


async def setup(rental_mode, *, price=None, vocabulary=None, count=4, positions=None):
    vocabulary = vocabulary or FactVocabulary(amenity_codes=frozenset(), catalog_other_codes=frozenset(),
                                             tenant_group_codes=frozenset(), municipality_zones=frozenset())
    pipeline = FactPipeline(SessionLocal, FactQueuePolicy(lease_seconds=60, max_attempts=2, retry_delay_seconds=1),
                            vocabulary, resolver_version="test-cards.v1")
    ledger = QuotaLedger(SessionLocal, LeasePolicy(reservation_seconds=60, running_seconds=60, recovery_grace_seconds=30))
    sessions = SearchSessions(ledger, SessionPolicy(inactivity_seconds=600), IntentVocabulary(
        vocabulary.amenity_codes, vocabulary.catalog_other_codes, vocabulary.municipality_zones))
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
        listings = [await _seed_listing_with_gallery(session, owner, rental_mode, str(i)) for i in range(count)]
        if positions is not None:
            from app.repositories.listings import point
            for listing, (longitude, latitude) in zip(listings, positions, strict=True):
                listing.location = point(longitude, latitude)
        if price is not None:
            for listing in listings:
                listing.monthly_price = price
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
        if price is not None:
            description += f". Rent {price} EUR monthly."
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
        if price is not None:
            from app.schemas.ai_listing_facts import FactObservation
            batch.facts.append(FactObservation.model_validate({
                "fact_id": uuid4(), "key": "price", "status": "explicit_allow",
                "typed_value": {"kind": "money", "amount": str(price), "currency": "EUR", "period": "monthly"},
                "qualifiers": {}, "origin": "source_text",
                "evidence": [{"field": "description", "quote": description, "start": 0, "end": len(description)}],
            }))
        await pipeline.complete(claim, batch, {"description": description})
        assert await QueryProofs(pipeline).prepare(ids[i])
    query = VerifiedCardSearch(pipeline, sessions, signing_key=b"synthetic-cards-key-not-a-secret32")
    return query, subject, owned.intent.session_id, ids, source_ids


@pytest.mark.parametrize("rental_mode", ["long", "holiday"])
async def test_existing_cards_top_gallery_and_both_cursor_directions(rental_mode, monkeypatch):
    from app.repositories import ai_verified_cards
    original = ai_verified_cards.compile_hard_match
    calls = []
    def compile_once(intent, vocabulary):
        calls.append(intent)
        return original(intent, vocabulary)
    monkeypatch.setattr(ai_verified_cards, "compile_hard_match", compile_once)
    query, subject, session_id, ids, _ = await setup(rental_mode)
    payload = ListingCardSearchRequest(rentalMode=rental_mode, sort="price_asc", limit=1)
    first = await query.search_owned(subject, session_id, 1, payload)
    assert len(calls) == 1
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


@pytest.mark.parametrize("change", ["insert", "delete", "replace"])
async def test_cursor_binds_prepared_proof_population(change):
    query, subject, session_id, ids, _ = await setup("long")
    if change == "insert":
        async with SessionLocal() as session, session.begin():
            await session.execute(delete(AiQueryProof).where(AiQueryProof.canonical_listing_id == ids[1]))
    payload = ListingCardSearchRequest(limit=1)
    first = await query.search_owned(subject, session_id, 1, payload)
    assert first.cards.nextCursor
    if change == "insert":
        assert await QueryProofs(query.pipeline).prepare(ids[1])
    else:
        async with SessionLocal() as session, session.begin():
            if change == "delete":
                await session.execute(delete(AiQueryProof).where(AiQueryProof.canonical_listing_id == ids[1]))
            else:
                await session.execute(update(AiQueryProof).where(AiQueryProof.canonical_listing_id == ids[1]).values(
                    signature="0" * 64))
    with pytest.raises(InvalidAICursor):
        await query.search_owned(subject, session_id, 1, payload.model_copy(update={"cursor": first.cards.nextCursor}))


async def test_identical_preparation_does_not_invalidate_cursor():
    query, subject, session_id, ids, _ = await setup("long")
    payload = ListingCardSearchRequest(limit=1)
    first = await query.search_owned(subject, session_id, 1, payload)
    assert await QueryProofs(query.pipeline).prepare(ids[1])
    second = await query.search_owned(subject, session_id, 1, payload.model_copy(update={"cursor": first.cards.nextCursor}))
    assert second.cards.total == first.cards.total


async def test_cursor_rejects_semantic_verifier_contract_change(monkeypatch):
    from app.repositories import ai_verified_cards
    query, subject, session_id, _, _ = await setup("long")
    payload = ListingCardSearchRequest(limit=1)
    first = await query.search_owned(subject, session_id, 1, payload)
    monkeypatch.setattr(ai_verified_cards, "PROOF_CONTRACT_VERSION", "next-verifier.test.v3")
    with pytest.raises(InvalidAICursor):
        await query.search_owned(subject, session_id, 1, payload.model_copy(update={"cursor": first.cards.nextCursor}))


@pytest.mark.parametrize("changes", [
    {"monthly_price": 900}, {"nightly_price": 200}, {"weekly_price": 1200},
    {"rental_mode": "holiday", "nightly_price": 55}, {"room_capacity": 2}, {"available_from": date(2027, 2, 1)},
    {"available_until": date(2027, 3, 1)}, {"pets_allowed": True},
])
async def test_canonical_card_change_invalidates_proof_before_count(changes):
    query, subject, session_id, ids, _ = await setup("long")
    async with SessionLocal() as session, session.begin():
        await session.execute(update(Listing).where(Listing.id == ids[1]).values(**changes))
    result = await query.search_owned(subject, session_id, 1, ListingCardSearchRequest())
    assert result.cards.total == 2
    assert str(ids[1]) not in {item.id for item in result.cards.items}


@pytest.mark.parametrize("change", ["insert", "update", "delete"])
async def test_canonical_room_details_change_invalidates_proof(change):
    query, subject, session_id, ids, _ = await setup("long")
    if change != "insert":
        async with SessionLocal() as session, session.begin():
            session.add(ListingRoomDetails(listing_id=ids[1], room_capacity_v2=2))
        assert await QueryProofs(query.pipeline).prepare(ids[1])
    async with SessionLocal() as session, session.begin():
        if change == "insert":
            session.add(ListingRoomDetails(listing_id=ids[1], room_capacity_v2=2))
        elif change == "update":
            await session.execute(update(ListingRoomDetails).where(ListingRoomDetails.listing_id == ids[1]).values(
                room_capacity_v2=5))
        else:
            await session.execute(delete(ListingRoomDetails).where(ListingRoomDetails.listing_id == ids[1]))
    result = await query.search_owned(subject, session_id, 1, ListingCardSearchRequest())
    assert result.cards.total == 2
    assert str(ids[1]) not in {item.id for item in result.cards.items}


async def test_public_price_change_cannot_recertify_stale_ai_budget():
    query, subject, session_id, ids, _ = await setup("long", price=500)
    async with SessionLocal() as session, session.begin():
        await session.execute(update(AISearchSession).where(AISearchSession.id == session_id).values(criteria={
            "budget": {"strength": "hard", "value": {"amount": "500", "currency": "EUR", "period": "monthly"}},
        }))
    before = await query.search_owned(subject, session_id, 1, ListingCardSearchRequest())
    assert before.cards.total == 4 and all(item.price == 500 for item in before.cards.items)
    async with SessionLocal() as session, session.begin():
        await session.execute(update(Listing).where(Listing.id == ids[1]).values(monthly_price=900))
    assert not await QueryProofs(query.pipeline).prepare(ids[1])
    await query.pipeline.reconcile_listing(ids[1])
    assert not await QueryProofs(query.pipeline).prepare(ids[1])
    after = await query.search_owned(subject, session_id, 1, ListingCardSearchRequest())
    assert after.cards.total == 3 and all(item.price == 500 for item in after.cards.items)


async def test_text_execution_uses_real_cards_and_atomic_session_quota_then_safe_replay():
    import hashlib

    from app.schemas.ai_search_intent import IntentPatch
    from app.schemas.ai_search_quota import QuotaOperation
    from app.services.ai_search_execution import TextSearchExecution
    query, subject, session_id, _, source_ids = await setup("long")
    class Parser:
        calls = 0
        async def parse(self, message, current):
            self.calls += 1
            return IntentPatch(schema_version="ai-search.v1", session_id=current.session_id,
                               expected_version=current.version)
    class Gate:
        calls = 0
        async def check(self, subject):
            self.calls += 1
    parser, gate = Parser(), Gate()
    execution = TextSearchExecution(query.sessions, parser, gate, query)
    message = "synthetic followup"
    operation = QuotaOperation(idempotency_key=uuid4(), channel="text",
        payload_sha256=hashlib.sha256(message.encode()).hexdigest(), session_id=session_id, expected_session_version=1)
    result = await execution.execute(subject, operation, message, ListingCardSearchRequest(limit=1))
    assert result.operation.status == "succeeded" and result.operation.receipt.count == result.cards.cards.total == 3
    assert result.operation.used == 1 and result.operation.reserved == 0
    assert (await query.sessions.get(subject, session_id)).intent.version == 2
    second = await query.search_owned(subject, session_id, 2,
        ListingCardSearchRequest(limit=1, cursor=result.cards.cards.nextCursor))
    assert second.cards.total == 3
    async with SessionLocal() as session, session.begin():
        await session.execute(update(ExternalListingSource).where(ExternalListingSource.id == source_ids[1]).values(
            raw_payload={"changed": True}))
    replay = await execution.execute(subject, operation, message, ListingCardSearchRequest(limit=1))
    assert replay.replay and replay.operation.receipt == result.operation.receipt
    assert replay.cards.cards.total == 2 and replay.operation.used == 1
    assert parser.calls == gate.calls == 1


async def test_verified_fact_budget_cannot_override_current_card_price_currency_from_or_mode():
    query, subject, session_id, ids, source_ids = await setup("long")
    pipeline = query.pipeline
    listing_id, source_id = ids[1], source_ids[1]
    description = "Monthly EUR600 long"
    async with SessionLocal() as session:
        _, authority = await pipeline._authority(session, listing_id, lock=False)
    request = SourceInput(source_record_id=source_id, canonical_listing_id=listing_id,
        content_hash=digest({"description": description}), snapshot_hash=authority[source_id].snapshot_hash,
        schema_version="ai-facts.v1", taxonomy_version="ai-search.v1", extractor_version="test-price.v2")
    await pipeline.observe(request)
    claim = await pipeline.claim()
    observations = []
    for key, value in (("price", {"kind": "money", "amount": "600", "currency": "EUR", "period": "monthly"}),
                       ("rental_mode", {"kind": "category", "value": "long"})):
        observations.append({"fact_id": uuid4(), "key": key, "status": "explicit_allow", "typed_value": value,
            "qualifiers": {}, "origin": "source_text", "evidence": [
                {"field": "description", "quote": description, "start": 0, "end": len(description)}]})
    batch = FactBatch.model_validate({"schema_version": claim.schema_version, "taxonomy_version": claim.taxonomy_version,
        "batch_id": uuid4(), "canonical_listing_id": listing_id, "source_record_id": source_id,
        "source_generation": claim.generation, "content_hash": claim.content_hash, "extractor_version": claim.extractor_version,
        "observed_at": datetime.now(UTC), "source_status": "active", "last_successful_check_at": None,
        "last_content_change_at": None, "last_check_error_at": None, "facts": observations})
    await pipeline.complete(claim, batch, {"description": description})
    # Reviewed proof.v2 rejects certification while canonical price is 725
    # and the source fact is 600. Certify only after they agree.
    assert not await QueryProofs(pipeline).prepare(listing_id)
    async with SessionLocal() as session, session.begin():
        await session.execute(update(Listing).where(Listing.id == listing_id).values(monthly_price=600))
    assert await QueryProofs(pipeline).prepare(listing_id)
    async with SessionLocal() as session, session.begin():
        await session.execute(update(AISearchSession).where(AISearchSession.id == session_id).values(criteria={
            "budget": {"strength": "hard", "value": {"amount": "700", "currency": "EUR", "period": "monthly"}},
            "rental_mode": {"strength": "hard", "value": "long"}}))
    page = await query.search_owned(subject, session_id, 1, ListingCardSearchRequest())
    assert page.cards.total == 1 and page.cards.items[0].price == 600
    async with SessionLocal() as session, session.begin():
        await session.execute(update(Listing).where(Listing.id == listing_id).values(monthly_price=725))
    assert (await query.search_owned(subject, session_id, 1, ListingCardSearchRequest())).cards.total == 0
    async with SessionLocal() as session, session.begin():
        await session.execute(update(Listing).where(Listing.id == listing_id).values(monthly_price=650))
    # Within budget still does not excuse stale, inconsistent source evidence.
    assert (await query.search_owned(subject, session_id, 1, ListingCardSearchRequest())).cards.total == 0
    assert not await QueryProofs(pipeline).prepare(listing_id)
    async with SessionLocal() as session, session.begin():
        await session.execute(update(Listing).where(Listing.id == listing_id).values(monthly_price=600))
    assert await QueryProofs(pipeline).prepare(listing_id)
    page = await query.search_owned(subject, session_id, 1, ListingCardSearchRequest())
    assert page.cards.total == 1 and page.cards.items[0].price == 600
    for changes in ({"source_price_currency": "USD"}, {"source_price_is_from": True}, {"rental_mode": "holiday", "nightly_price": 55}):
        async with SessionLocal() as session, session.begin():
            await session.execute(update(Listing).where(Listing.id == listing_id).values(**changes))
        assert (await query.search_owned(subject, session_id, 1, ListingCardSearchRequest())).cards.total == 0
        async with SessionLocal() as session, session.begin():
            await session.execute(update(Listing).where(Listing.id == listing_id).values(
                source_price_currency=None, source_price_is_from=None, rental_mode="long", nightly_price=None))


async def test_ai_map_uses_same_guards_before_markers_clusters_and_public_visibility():
    from app.repositories.listings import search_public_map
    from app.schemas.listings import ListingMapRequest
    query, subject, session_id, ids, source_ids = await setup("long")
    bounds = {"north": 28.5, "south": 27.5, "east": -16.6, "west": -16.9, "zoom": 14}
    payload = ListingMapRequest(**bounds)
    result = await query.map_owned(subject, session_id, 1, payload)
    assert {item.id for item in result.map.items} == {str(i) for i in ids[1:]}
    assert next(item for item in result.map.items if item.id == str(ids[1])).promoted
    assert result.intent_hash == (await query.search_owned(subject, session_id, 1, ListingCardSearchRequest())).intent_hash
    with pytest.raises(SessionError, match="SESSION_NOT_FOUND"):
        await query.map_owned(QuotaSubject(kind="guest", id=uuid4()), session_id, 1, payload)
    with pytest.raises(SessionError, match="SESSION_VERSION_CONFLICT"):
        await query.map_owned(subject, session_id, 0, payload)
    async with SessionLocal() as session, session.begin():
        await session.execute(update(ExternalListingSource).where(ExternalListingSource.id == source_ids[1]).values(
            raw_payload={"changed": True}))
    clustered = await query.map_owned(subject, session_id, 1, ListingMapRequest(**(bounds | {"zoom": 8})))
    assert len(clustered.map.items) == 1 and clustered.map.items[0].type == "cluster"
    assert clustered.map.items[0].count == 2 and not clustered.map.items[0].promoted
    async with SessionLocal() as session:
        manual = await search_public_map(session, payload)
        assert len(manual.items) == 4
    async with SessionLocal() as session, session.begin():
        await session.execute(update(User).values(blocked=True))
    assert not (await query.map_owned(subject, session_id, 1, payload)).map.items


async def test_dense_ai_map_thresholds_edges_and_live_proof_changes(record_property):
    import asyncio
    import json
    from time import perf_counter

    from sqlalchemy import event

    from app.schemas.listings import ListingMapRequest

    bounds = {"north": 28.5, "south": 27.5, "east": -16.6, "west": -16.9}
    center = (-16.733, 28.061)
    # Inclusive viewport edges occupy all four extreme cells; the rest share
    # one center cell. Row zero has incompatible pets and must never count.
    positions = [center, (-16.9, 27.5), (-16.6, 27.5), (-16.9, 28.5), (-16.6, 28.5)] + [center] * 298
    query, subject, sid, ids, source_ids = await setup("long", count=303, positions=positions)
    async with SessionLocal() as session, session.begin():
        first = await session.get(Listing,ids[0])
        owner = await session.get(User,first.owner_user_id)
        outside = await _seed_listing_with_gallery(session,owner,"long","plan-unrelated")
        outside.status = "draft"
        await session.flush()
        await session.execute(ExternalListingSource.__table__.insert(),[{
            "source_name":"plan-unrelated","external_id":str(i),"source_url":f"https://example.invalid/plan/{i}",
            "canonical_listing_id":outside.id,"fingerprint":digest(str(i)),"current_status":"active"
        } for i in range(2048)])
    async with SessionLocal() as session, session.begin():
        for table in ("listings","external_listing_sources","ai_fact_sources"):
            await session.execute(text(f"ANALYZE {table}"))
    timings = []
    plans = []
    original_hash = None

    async def read(zoom, expected):
        nonlocal original_hash
        started = perf_counter()
        captured = []
        engine = SessionLocal.kw["bind"]
        inspect_plan = len(expected) in {32,128,300,301} and zoom in {8,13}
        def capture(conn,cursor,statement,parameters,context,executemany):
            if getattr(getattr(context.compiled,"statement",None),"is_select",False):
                captured.append((statement,parameters))
        if inspect_plan:
            event.listen(engine.sync_engine,"before_cursor_execute",capture)
        try:
            result = await query.map_owned(subject, sid, 1, ListingMapRequest(**bounds, zoom=zoom))
        finally:
            if inspect_plan:
                event.remove(engine.sync_engine,"before_cursor_execute",capture)
        timings.append({"valid": len(expected), "zoom": zoom, "seconds": round(perf_counter() - started, 6)})
        if inspect_plan:
            def authorities(node):
                return ([node] if node.get("Relation Name") == "external_listing_sources" else []) + [
                    item for child in node.get("Plans",[]) for item in authorities(child)]
            case = {"valid":len(expected),"zoom":zoom,"authority_plans":0,"loops":0,"visited_rows":0,"buffer_touches":0,"execution_ms":0,"node_types":set()}
            async with SessionLocal() as session, session.begin():
                await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
                await session.execute(text("SET LOCAL jit = off"))
                raw = await (await session.connection()).get_raw_connection()
                for sql,parameters in captured:
                    plan = await raw.driver_connection.fetchval("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) "+sql,*parameters)
                    plan = json.loads(plan) if isinstance(plan,str) else plan
                    nodes = authorities(plan[0]["Plan"])
                    if not nodes:
                        continue
                    case["authority_plans"] += 1
                    case["execution_ms"] += plan[0]["Execution Time"]
                    for node in nodes:
                        case["loops"] += node["Actual Loops"]
                        case["visited_rows"] += node["Actual Loops"]*(node["Actual Rows"]+node.get("Rows Removed by Filter",0))
                        case["buffer_touches"] += node.get("Shared Hit Blocks",0)+node.get("Shared Read Blocks",0)
                        case["node_types"].add(node["Node Type"])
            assert case["authority_plans"] == 1,case
            assert "Seq Scan" not in case["node_types"],case
            assert case["loops"] <= 32*(len(expected)+1),case
            assert case["visited_rows"] <= 32*(len(expected)+1),case
            assert case["buffer_touches"] <= 256*(len(expected)+1),case
            case["node_types"] = sorted(case["node_types"])
            plans.append(case)
        original_hash = original_hash or result.intent_hash
        assert result.intent_hash == original_hash
        if zoom >= 13 and len(expected) <= 300:
            assert {item.id for item in result.map.items} == {str(value) for value in expected}
            assert all(item.type == "listing" for item in result.map.items)
            assert {item.id for item in result.map.items if item.promoted} == ({str(ids[1])} & {str(i) for i in expected})
        else:
            assert all(item.type == "cluster" for item in result.map.items)
            assert sum(item.count for item in result.map.items) == len(expected)
        return result

    for count in (302, 301, 300, 128, 32, 299, 0):
        async with SessionLocal() as session, session.begin():
            await session.execute(update(Listing).where(Listing.id.in_(ids)).values(status="published"))
            await session.execute(update(Listing).where(Listing.id.in_(ids[count + 1:])).values(status="draft"))
        expected = ids[1:count + 1]
        for zoom in (8, 12, 13, 21):
            result = await read(zoom, expected)
            if count and (zoom < 13 or count > 300):
                cells = {item.id: item for item in result.map.items}
                assert set(cells) == {"0:0", "19:0", "0:19", "19:19", "11:11"}
                assert cells["0:0"].count == 1 and cells["0:0"].promoted
                assert not any(item.promoted for key, item in cells.items() if key != "0:0")

    # Same intent, changed live catalog: invalidate many sources and proofs,
    # hide another group, then alternate/concurrently read marker and cluster
    # modes. Filtering must precede both the 301 probe and full aggregation.
    async with SessionLocal() as session, session.begin():
        await session.execute(update(Listing).where(Listing.id.in_(ids)).values(status="published"))
        await session.execute(update(ExternalListingSource).where(ExternalListingSource.id.in_(source_ids[1:102])).values(
            raw_payload={"changed": True}))
        await session.execute(update(Listing).where(Listing.id.in_(ids[102:202])).values(status="draft"))
        await session.execute(delete(AiQueryProof).where(AiQueryProof.canonical_listing_id.in_(ids[202:252])))
    results = await asyncio.gather(*(read(zoom, ids[252:]) for zoom in (8, 21, 12, 13)))
    assert not any(item.promoted for result in results for item in result.map.items)
    # Synthetic timing evidence only: no production latency/SLO assertion.
    record_property("synthetic_map_timings", json.dumps(timings))
    record_property("synthetic_map_plans", json.dumps(plans))


@pytest.mark.parametrize("mode,period,column,display", [("long", "weekly", "weekly_price", 725),
    ("holiday", "monthly", "monthly_price", 55)])
async def test_budget_response_explains_confirmed_amount_and_native_display_period(mode, period, column, display):
    from fastapi.encoders import jsonable_encoder
    query, subject, session_id, ids, source_ids = await setup(mode)
    listing_id, source_id = ids[1], source_ids[1]
    pipeline = query.pipeline
    async with SessionLocal() as session, session.begin():
        await session.execute(update(Listing).where(Listing.id == listing_id).values(**{column: 200}))
        _, authority = await pipeline._authority(session, listing_id, lock=False)
    description = f"Confirmed EUR200 {period}"
    await pipeline.observe(SourceInput(source_record_id=source_id, canonical_listing_id=listing_id,
        content_hash=digest({"description": description}), snapshot_hash=authority[source_id].snapshot_hash,
        schema_version="ai-facts.v1", taxonomy_version="ai-search.v1", extractor_version="test-price-period.v1"))
    claim = await pipeline.claim()
    batch = FactBatch.model_validate({"schema_version": claim.schema_version, "taxonomy_version": claim.taxonomy_version,
        "batch_id": uuid4(), "canonical_listing_id": listing_id, "source_record_id": source_id,
        "source_generation": claim.generation, "content_hash": claim.content_hash, "extractor_version": claim.extractor_version,
        "observed_at": datetime.now(UTC), "source_status": "active", "last_successful_check_at": None,
        "last_content_change_at": None, "last_check_error_at": None, "facts": [{"fact_id": uuid4(), "key": "price",
        "status": "explicit_allow", "typed_value": {"kind": "money", "amount": "200", "currency": "EUR", "period": period},
        "qualifiers": {}, "origin": "source_text", "evidence": [
            {"field": "description", "quote": description, "start": 0, "end": len(description)}]}]})
    await pipeline.complete(claim, batch, {"description": description})
    assert await QueryProofs(pipeline).prepare(listing_id)
    async with SessionLocal() as session, session.begin():
        await session.execute(update(AISearchSession).where(AISearchSession.id == session_id).values(criteria={
            "budget": {"strength": "hard", "value": {"amount": "200", "currency": "EUR", "period": period}}}))
    response = jsonable_encoder(await query.search_owned(subject, session_id, 1, ListingCardSearchRequest()))
    assert response["cards"]["total"] == 1
    assert response["cards"]["items"][0]["price"] == display
    assert response["budget_prices"] == [{"listing_id": str(listing_id), "matched_amount": 200,
        "matched_period": period, "display_amount": display, "display_period": "monthly" if mode == "long" else "nightly",
        "currency": "EUR", "confirmation": "current_source_proof"}]




@pytest.mark.parametrize("capacity,residents,spots,fact_residents,expected", [
    (3, 2, 2, None, False),  # Review reproduction: no optional occupancy fact.
    (3, 1, 2, None, True),
    (3, 1, 2, 1, True),
    (3, 1, 2, 2, False),   # Individually present facts must also agree jointly.
    (3, 2, 2, 2, False),
    (3, None, 2, None, False),
    (None, 1, 2, None, False),
    (3, 3, 2, None, False),
    (3, 4, 2, None, False),
])
async def test_party_requires_current_available_spots(capacity, residents, spots, fact_residents, expected):
    query, subject, session_id, ids, source_ids = await setup("long")
    listing_id, source_id = ids[1], source_ids[1]
    async with SessionLocal() as session, session.begin():
        await session.execute(update(Listing).where(Listing.id == listing_id).values(room_capacity=None))
        session.add(ListingRoomDetails(listing_id=listing_id, room_capacity_v2=capacity, current_room_residents=residents))
        await session.execute(update(AISearchSession).where(AISearchSession.id == session_id).values(criteria={
            "party": {"strength": "hard", "value": {"adults": 2, "children": 0, "relationship": "unspecified"}},
        }))
    fields = {"description": "Synthetic capacity and free-place evidence"}
    async with SessionLocal() as session:
        _, authority = await query.pipeline._authority(session, listing_id, lock=False)
    source = SourceInput(source_record_id=source_id, canonical_listing_id=listing_id,
        content_hash=digest(fields), snapshot_hash=authority[source_id].snapshot_hash,
        schema_version="ai-facts.v1", taxonomy_version="ai-search.v1", extractor_version="inventory-test.v1")
    await query.pipeline.observe(source)
    claim = await query.pipeline.claim()
    inventory = {"capacity_total": 3, "available_spots": spots}
    if fact_residents is not None:
        inventory["current_room_residents"] = fact_residents
    batch = FactBatch.model_validate({
        "schema_version": claim.schema_version, "taxonomy_version": claim.taxonomy_version,
        "batch_id": uuid4(), "canonical_listing_id": listing_id, "source_record_id": source_id,
        "source_generation": claim.generation, "content_hash": claim.content_hash,
        "extractor_version": claim.extractor_version, "observed_at": datetime.now(UTC), "source_status": "active",
        "last_successful_check_at": None, "last_content_change_at": None, "last_check_error_at": None,
        "facts": [{"fact_id": uuid4(), "key": key, "status": "explicit_allow",
            "typed_value": {"kind": "quantity", "value": value, "unit": "persons"},
            "qualifiers": {"inventory_scope": "rented_unit"}, "origin": "source_text",
            "evidence": [{"field": "description", "quote": fields["description"], "start": 0,
                          "end": len(fields["description"])}]} for key, value in inventory.items()],
    })
    await query.pipeline.complete(claim, batch, fields)
    assert await QueryProofs(query.pipeline).prepare(listing_id) is expected
    page = await query.search_owned(subject, session_id, 1, ListingCardSearchRequest())
    assert page.cards.total == int(expected)
    assert [item.id for item in page.cards.items] == ([str(listing_id)] if expected else [])
    if expected:
        # Re-preparation and reconcile cannot bless stale inventory later.
        async with SessionLocal() as session, session.begin():
            await session.execute(update(ListingRoomDetails).where(ListingRoomDetails.listing_id == listing_id).values(
                current_room_residents=2))
        assert not await QueryProofs(query.pipeline).prepare(listing_id)
        await query.pipeline.reconcile_listing(listing_id)
        assert not await QueryProofs(query.pipeline).prepare(listing_id)
        assert (await query.search_owned(subject, session_id, 1, ListingCardSearchRequest())).cards.total == 0


@pytest.mark.parametrize("mutation", ["raw_payload", "status", "moderation", "owner", "top"])
async def test_live_cursor_rechecks_eligibility_and_order_between_pages(mutation):
    query, subject, session_id, ids, source_ids = await setup("long")
    payload = ListingCardSearchRequest(limit=1)
    first = await query.search_owned(subject, session_id, 1, payload)
    assert first.cards.total == 3 and first.cards.items[0].id == str(ids[1])
    async with SessionLocal() as session, session.begin():
        saved_proofs = (await session.execute(select(AiQueryProof.canonical_listing_id, AiQueryProof.signature))).all()
        if mutation == "raw_payload":
            await session.execute(update(ExternalListingSource).where(ExternalListingSource.id == source_ids[2]).values(
                raw_payload={"changed": True}))
        elif mutation == "status":
            await session.execute(update(ExternalListingSource).where(ExternalListingSource.id == source_ids[2]).values(
                current_status="removed"))
        elif mutation == "moderation":
            session.add(ListingRestriction(listing_id=ids[2], reason="Synthetic restriction",
                                           starts_at=datetime.now(UTC) - timedelta(seconds=1)))
        elif mutation == "owner":
            await session.execute(update(User).values(blocked=True))
        else:
            session.add(ListingPromotion(listing_id=ids[2], starts_at=datetime.now(UTC) - timedelta(seconds=1),
                ends_at=datetime.now(UTC) + timedelta(days=1), boosted_at=datetime.now(UTC), payment_managed=False))
    page = await query.search_owned(subject, session_id, 1, payload.model_copy(update={"cursor": first.cards.nextCursor}))
    assert page.cards.total == (0 if mutation == "owner" else 3 if mutation == "top" else 2)
    assert str(ids[2]) not in {item.id for item in page.cards.items}
    async with SessionLocal() as session:
        assert set((await session.execute(select(AiQueryProof.canonical_listing_id, AiQueryProof.signature))).all()) == set(saved_proofs)
        assert await session.scalar(select(func.count()).select_from(AIUsageDay)) == 0
    if mutation == "top":
        # The row moved before the seek point. Only a fresh first page discovers
        # it; signed cursors never claim stable membership/order across pages.
        fresh = await query.search_owned(subject, session_id, 1, payload)
        assert fresh.cards.items[0].id == str(ids[2])


@pytest.mark.parametrize("mutation", ["raw_payload", "status"])
async def test_live_cursor_requires_restart_for_newly_eligible_rows_before_seek(mutation):
    query, subject, session_id, ids, source_ids = await setup("long")
    async with SessionLocal() as session, session.begin():
        await session.execute(update(ExternalListingSource).where(ExternalListingSource.id == source_ids[1]).values(
            **({"raw_payload": {"changed": True}} if mutation == "raw_payload" else {"current_status": "removed"})))
    payload = ListingCardSearchRequest(limit=1)
    first = await query.search_owned(subject, session_id, 1, payload)
    assert first.cards.total == 2 and first.cards.nextCursor
    async with SessionLocal() as session, session.begin():
        # Restore exact source equality without modifying the cached proof or
        # canonical listing: the promoted row becomes eligible before our seek.
        await session.execute(update(ExternalListingSource).where(ExternalListingSource.id == source_ids[1]).values(
            **({"raw_payload": {}} if mutation == "raw_payload" else {"current_status": "active"})))
    second = await query.search_owned(subject, session_id, 1, payload.model_copy(update={"cursor": first.cards.nextCursor}))
    assert second.cards.total == 3 and str(ids[1]) not in {item.id for item in second.cards.items}
    fresh = await query.search_owned(subject, session_id, 1, payload)
    assert fresh.cards.total == 3 and fresh.cards.items[0].id == str(ids[1])
