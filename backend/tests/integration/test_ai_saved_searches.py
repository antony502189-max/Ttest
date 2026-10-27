"""Full legacy/PostGIS schema: saved dry-run parity and current rematch guards."""
import hashlib
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, update
from test_ai_verified_cards import setup

from app.db.session import SessionLocal
from app.models import ExternalListingSource, Listing, MailOutbox, Notification, SavedSearch, User
from app.models.ai_fact_pipeline import AiFactRematchEvent
from app.models.ai_query_proof import AiQueryProof
from app.models.ai_search_quota import AISearchRequest, AIUsageDay
from app.models.ai_search_session import AISearchResult, AISearchSession
from app.models.moderation import ListingRestriction, UserRestriction
from app.repositories.ai_saved_searches import RegisteredAISearches, SavedAIError
from app.schemas.ai_listing_facts import FactVocabulary
from app.schemas.ai_search_intent import Criteria, IntentPatch
from app.schemas.ai_search_quota import QuotaOperation, QuotaSubject
from app.schemas.listings import ListingCardSearchRequest, ListingMapRequest
from app.services.ai_search_execution import TextSearchExecution

pytestmark = pytest.mark.integration
PET = {"pets": {"strength": "hard", "value": [{"species": "dog", "size": "small", "count": 1}]}}


async def configured():
    vocabulary = FactVocabulary(amenity_codes=frozenset({"wifi"}), catalog_other_codes=frozenset(),
                                tenant_group_codes=frozenset(), municipality_zones=frozenset())
    query, _, _, ids, sources = await setup("long", vocabulary=vocabulary)
    async with SessionLocal.begin() as conn:
        user = User(email="saved-ai-tenant@example.test", name="Synthetic Tenant", initials="ST", email_verified=True)
        conn.add(user)
        await conn.flush()
        subject = QuotaSubject(kind="auth", id=user.id)
    return query, RegisteredAISearches(query.sessions, query.pipeline), subject, ids, sources


async def saved_result(query, repo, subject, criteria):
    initial = await query.sessions.create(subject)
    patch = IntentPatch.model_validate_json(json.dumps({"schema_version": "ai-search.v1",
        "session_id": str(initial.intent.session_id), "expected_version": 0, "set": criteria}))
    service = TextSearchExecution(query.sessions, SimpleNamespace(parse=AsyncMock(return_value=patch)),
                                  SimpleNamespace(check=AsyncMock()), query)
    operation = QuotaOperation(idempotency_key=uuid4(), channel="text", session_id=initial.intent.session_id,
        expected_session_version=0, payload_sha256=hashlib.sha256(b"synthetic").hexdigest())
    answer = await service.execute(subject, operation, "synthetic", ListingCardSearchRequest())
    assert answer.operation.status == "succeeded"
    return await repo.save(subject, answer.operation.receipt.result_ref), answer.operation.receipt.result_ref


async def test_every_hard_criterion_has_card_map_saved_dryrun_parity_without_extra_debit():
    query, repo, subject, ids, _ = await configured()
    values = {
        "rental_mode": "long", "budget": {"amount": "800", "currency": "EUR", "period": "monthly"},
        "geography": {"province_code": "38", "municipality_code": "38001"}, "accommodation": {"kind": "room"},
        "party": {"adults": 1, "children": 0, "relationship": "unspecified"},
        "pets": PET["pets"]["value"], "smoking": {"scope": "balcony"}, "furnished": False,
        "bills_included": False, "deposit": {"kind": "quantity", "value": 1, "unit": "months"},
        "balcony": False, "terrace": True, "amenities": ["wifi"],
        "dates": {"check_in": "2026-11-01", "check_out": "2026-11-03"}, "stay": {"value": 2, "unit": "nights"},
    }
    assert set(values) == set(Criteria.model_fields)
    for name, value in values.items():
        snapshot, result_ref = await saved_result(query, repo, subject, {name: {"strength": "hard", "value": value}})
        cards = await query.query_result(subject, result_ref, ListingCardSearchRequest(limit=50))
        markers = await query.map_result(subject, result_ref, ListingMapRequest(
            north=29, south=27, east=-15, west=-18, zoom=19))
        card_ids = {item.id for item in cards.cards.items}
        marker_ids = {str(item.id) for item in markers.map.items}
        assert marker_ids == card_ids
        decisions = [await repo.dry_run(subject, snapshot.id, listing_id) for listing_id in ids]
        assert {str(item.listing_id) for item in decisions if item.status == "matched"} == card_ids
        assert all(item.delivery_enabled is False for item in decisions)
    async with SessionLocal() as conn:
        assert await conn.scalar(select(func.count()).select_from(AISearchRequest)) == 15
        assert await conn.scalar(select(func.sum(AIUsageDay.used))) == 15
        assert await conn.scalar(select(func.count()).select_from(Notification)) == 0
        assert await conn.scalar(select(func.count()).select_from(MailOutbox)) == 0


async def test_rematch_reloads_current_sources_proofs_moderation_and_saved_state():
    query, repo, subject, ids, sources = await configured()
    saved, _ = await saved_result(query, repo, subject, PET)
    async with SessionLocal() as conn:
        events = (await conn.scalars(select(AiFactRematchEvent).where(AiFactRematchEvent.canonical_listing_id == ids[1]))).all()
        event_id = events[0].id
        event_count = await conn.scalar(select(func.count()).select_from(AiFactRematchEvent))
    first = await repo.dry_run_event(subject, saved.id, event_id)
    assert first.status == "matched" and first.delivery_enabled is False
    assert await repo.dry_run_event(subject, saved.id, event_id) == first
    async with SessionLocal.begin() as conn:
        # Synthetic out-of-order signal with an unauthoritative revision/hash:
        # a dry run must inspect current proof, never claim it as verified input.
        later_id = uuid4()
        conn.add(AiFactRematchEvent(id=later_id, canonical_listing_id=ids[1],
            feature_revision=events[0].feature_revision + 1, input_hash="b" * 64, created_at=datetime.now(UTC)))
    assert await repo.dry_run_event(subject, saved.id, later_id) == first
    assert await repo.dry_run_event(subject, saved.id, event_id) == first
    async with SessionLocal.begin() as conn:
        # New current source data with no catalog revision bump must invalidate
        # even an old matching event and proof; event hash is not authority.
        await conn.execute(update(ExternalListingSource).where(ExternalListingSource.id == sources[1]).values(raw_payload={"changed": True}))
    assert (await repo.dry_run_event(subject, saved.id, event_id)).status == "not_verified_or_ineligible"
    assert (await repo.dry_run_event(subject, saved.id, later_id)).status == "not_verified_or_ineligible"
    async with SessionLocal.begin() as conn:
        await conn.execute(update(ExternalListingSource).where(ExternalListingSource.id == sources[1]).values(raw_payload={}))
        conn.add(ListingRestriction(listing_id=ids[1], reason="synthetic", starts_at=datetime.now(UTC) - timedelta(hours=1)))
    assert (await repo.dry_run_event(subject, saved.id, event_id)).status == "not_verified_or_ineligible"
    disabled = await repo.set_enabled(subject, saved.id, saved.revision, False)
    assert (await repo.dry_run_event(subject, saved.id, event_id)).status == "disabled"
    async with SessionLocal.begin() as conn:
        # Delete original conversations; the registered snapshot is independent.
        await conn.execute(delete(AISearchResult))
        await conn.execute(delete(AISearchSession))
    assert (await repo.get(subject, saved.id)).intent_hash == saved.intent_hash
    async with SessionLocal() as conn:
        assert await conn.scalar(select(func.count()).select_from(AiFactRematchEvent)) == event_count + 1
        assert await conn.scalar(select(func.count()).select_from(Notification)) == 0
        assert await conn.scalar(select(func.count()).select_from(MailOutbox)) == 0
        assert await conn.scalar(select(func.sum(AIUsageDay.used))) == 1
    async with SessionLocal.begin() as conn:
        await conn.execute(delete(SavedSearch).where(SavedSearch.id == saved.id))
    with pytest.raises(SavedAIError, match="SAVED_AI_NOT_FOUND"):
        await repo.dry_run_event(subject, disabled.id, event_id)


@pytest.mark.parametrize("change", ["proof", "hidden", "owner_blocked", "reader_blocked", "reader_restricted"])
async def test_dryrun_current_eligibility_and_missing_proof_never_deliver(change):
    query, repo, subject, ids, _ = await configured()
    saved, _ = await saved_result(query, repo, subject, PET)
    async with SessionLocal.begin() as conn:
        if change == "proof":
            await conn.execute(delete(AiQueryProof).where(AiQueryProof.canonical_listing_id == ids[1]))
        elif change == "hidden":
            await conn.execute(update(Listing).where(Listing.id == ids[1]).values(status="hidden"))
        elif change == "owner_blocked":
            owner_id = await conn.scalar(select(Listing.owner_user_id).where(Listing.id == ids[1]))
            await conn.execute(update(User).where(User.id == owner_id).values(blocked=True))
        elif change == "reader_blocked":
            await conn.execute(update(User).where(User.id == subject.id).values(blocked=True))
        else:
            conn.add(UserRestriction(user_id=subject.id, restriction_type="full", reason="synthetic"))
    if change.startswith("reader"):
        with pytest.raises(SavedAIError, match="REGISTERED_USER_UNAVAILABLE"):
            await repo.dry_run(subject, saved.id, ids[1])
    else:
        assert (await repo.dry_run(subject, saved.id, ids[1])).status == "not_verified_or_ineligible"
