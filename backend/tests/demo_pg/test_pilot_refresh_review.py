"""Private disposable PG only; no production importer, provider or erasure reset."""

import copy
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_seed import seed_database as seed_database  # noqa: PLC0414 - pytest fixture export
from test_seed import snapshot

from app.models import Listing
from app.repositories.ai_verified_cards import SourceCoverageUnavailable
from app.services.ai_erasure_journal import ErasureJournal
from demo.entry import pipeline
from demo.seed_state import CARD_FIELDS, seed_catalog
from pilot.budget import PilotBudget
from pilot.catalog_health import CatalogHealth, cohort_hash
from pilot.guarded_cards import GuardedCards
from pilot.readiness import CatalogReadiness
from pilot.refresh import refresh

pytestmark = pytest.mark.integration


async def test_composite_housing_refresh_followups_map_and_replay_keep_one_intent(seed_database):
    import hashlib
    from uuid import uuid4

    import httpx
    from pydantic import SecretStr

    from app.repositories.ai_search_quota import QuotaLedger
    from app.repositories.ai_search_sessions import IntentVocabulary, SearchSessions, SessionPolicy
    from app.schemas.ai_search_intent import SessionCreate, apply_patch
    from app.schemas.ai_search_quota import LeasePolicy, QuotaOperation, QuotaSubject
    from app.schemas.listings import ListingCardSearchRequest, ListingMapRequest
    from app.services.ai_decision_intent import DecisionDeepSeekIntent
    from app.services.ai_deepseek_intent import DeepSeekPolicy
    from app.services.ai_housing_input import HousingGate, housing_patch, validate_housing_result
    from app.services.ai_search_execution import TextSearchExecution

    engine, factory, state, original, health, incoming = await setup(seed_database)
    try:
        for i, row in enumerate(incoming["records"]):
            row["source"]["normalized_payload"]["housing_source"] = {
                "city": "san_cristobal_de_la_laguna", "html": '<div class="seccionesFichaAnuncio"><div class="contCaract"><ul><li>Amueblada</li></ul></div><div class="contTwocols"><ul><li>Incluye gastos</li><li>Fianza: ' + ("0" if i < 2 else "200") + ' €</li></ul></div></div>'}
        await refresh(factory, original, incoming, health=health)
        async with factory() as conn:
            stored = (await conn.execute(text("SELECT normalized_payload FROM external_listing_sources"))).scalars().all()
            assert all("housing_source" not in r and "html" not in json.dumps(r) for r in stored)
        facts = pipeline(factory)
        vocab = IntentVocabulary(facts.vocabulary.amenity_codes, frozenset(), frozenset())
        sessions = SearchSessions(QuotaLedger(factory, LeasePolicy(reservation_seconds=60, running_seconds=60, recovery_grace_seconds=30)),
            SessionPolicy(inactivity_seconds=86400), vocab)
        cards = GuardedCards(facts, sessions, signing_key=b"q" * 32, health=health)
        ready = CatalogReadiness(facts, health)
        subject = QuotaSubject(kind="guest", id=uuid4())
        owned = await sessions.create(subject, SessionCreate(rental_mode="long"))
        calls = []

        async def handler(request):
            data = json.loads(request.content)
            message = json.loads(data["messages"][1]["content"])
            assert str(subject.id) not in json.dumps(message) and str(owned.intent.session_id) not in json.dumps(message)
            calls.append(message)
            decision = {"status": "patch", "patch": json.loads(message["text"].split(": ", 1)[1])}
            return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(decision)}}]})

        adapter = DecisionDeepSeekIntent(transport=httpx.MockTransport(handler), key=SecretStr("offline-only"),
            policy=DeepSeekPolicy(model="deepseek-flash", timeout_seconds=8, total_budget_seconds=10,
                max_tokens=1024, max_attempts=1, retry_delay_seconds=0, max_response_bytes=65536), gate=HousingGate(vocab))

        class Parser:
            async def parse(self, text, current):
                expected = housing_patch(text, current, vocab)
                await ready.require_intent(apply_patch(current, expected))
                patch = await adapter.parse(text, current)
                validate_housing_result(current, patch, expected)
                return patch

        class Gate:
            async def check(self, subject):
                pass

        execution = TextSearchExecution(sessions, Parser(), Gate(), cards)
        async def message(text, version):
            operation = QuotaOperation(idempotency_key=uuid4(), channel="text", payload_sha256=hashlib.sha256(text.encode()).hexdigest(),
                session_id=owned.intent.session_id, expected_session_version=version)
            result = await execution.execute(subject, operation, text, ListingCardSearchRequest())
            return result, operation

        utterance = "a room in La Laguna under 700 euros per month, furnished, bills included, deposit 0 euros"
        first, operation = await message(utterance, 0)
        assert first.operation.status == "succeeded" and first.cards.cards.total == 2
        replay = await execution.execute(subject, operation, utterance, ListingCardSearchRequest())
        assert replay.replay and len(calls) == 1
        second, _ = await message("now under 360 euros per month", 1)
        assert second.operation.status == "succeeded" and second.cards.cards.total == 1
        current = (await sessions.get(subject, owned.intent.session_id)).intent
        before = current.criteria.model_dump(mode="json", exclude_none=True)
        assert set(before) == {"rental_mode", "budget", "geography", "accommodation", "furnished", "bills_included", "deposit"}
        failed, _ = await message("2 adults, 0 children", 2)
        assert failed.operation.failure_code == "SOURCE_COVERAGE_UNAVAILABLE" and failed.operation.remaining == second.operation.remaining
        assert (await sessions.get(subject, owned.intent.session_id)).intent.criteria.model_dump(mode="json", exclude_none=True) == before
        assert len(calls) == 2
        restored = await cards.query_result(subject, first.operation.receipt.result_ref, ListingCardSearchRequest())
        assert restored.cards.total == 2 and restored.intent_hash == first.cards.intent_hash
        mapped = await cards.map_result(subject, second.operation.receipt.result_ref,
            ListingMapRequest(north=29, south=27, east=-16, west=-17, zoom=18))
        assert len(mapped.map.items) == 1 and mapped.intent_hash == second.cards.intent_hash
        assert len(calls) == 2 and PilotBudget(state / "provider.sqlite3").summary()["attempts"] == 0
    finally:
        await engine.dispose()


async def setup(seed_database):
    dsn, name, _, state = seed_database
    engine = create_async_engine(dsn, pool_size=3, max_overflow=0)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    original = snapshot()
    original["records"] = original["records"][:3]
    for r in original["records"]:
        for key in CARD_FIELDS:
            r["listing"].setdefault(key, None)
        r["listing"].update(
            room_type="Habitación individual",
            amenities=["wifi"],
            restrictions=[],
            external_image_urls=[],
            furnished=True,
            pets_allowed=False,
            primary_source_url=r["source"]["source_url"],
            source_price_text=r["source"]["source_price_text"],
            source_price_currency="EUR",
            source_price_period="month",
            source_price_is_from=False,
        )
    await seed_catalog(
        engine,
        factory,
        original,
        state,
        lambda *, initialize: ErasureJournal(state / "erasure.sqlite3", b"s" * 32, initialize=initialize),
        database_name=name,
        budget_factory=PilotBudget,
    )
    health = CatalogHealth(state / "catalog-health.json", cohort_hash(original))
    incoming = envelope(original)
    return engine, factory, state, original, health, incoming


async def assert_visible(factory, health, count):
    from uuid import uuid4

    from app.repositories.ai_search_quota import QuotaLedger
    from app.repositories.ai_search_sessions import IntentVocabulary, SearchSessions, SessionPolicy
    from app.schemas.ai_search_intent import SessionCreate
    from app.schemas.ai_search_quota import LeasePolicy, QuotaSubject
    from app.schemas.listings import ListingCardSearchRequest

    sessions = SearchSessions(
        QuotaLedger(factory, LeasePolicy(reservation_seconds=60, running_seconds=60, recovery_grace_seconds=30)),
        SessionPolicy(inactivity_seconds=86400),
        IntentVocabulary(frozenset(), frozenset(), frozenset()),
    )
    subject = QuotaSubject(kind="guest", id=uuid4())
    owned = await sessions.create(subject, SessionCreate(rental_mode="long"))
    cards = GuardedCards(pipeline(factory), sessions, signing_key=b"q" * 32, health=health)
    result = await cards.search_owned(subject, owned.intent.session_id, 0, ListingCardSearchRequest())
    assert result.cards.total == count


def envelope(original, keep=None):
    records = copy.deepcopy(original["records"])
    keep = set(range(len(records))) if keep is None else set(keep)
    return {
        "schema": "pilot-cohort.v2",
        "snapshot_at": datetime.now(UTC).isoformat(),
        "cohort": [{"listing_id": r["listing"]["id"], "source_id": r["source"]["id"]} for r in records],
        "records": [r for i, r in enumerate(records) if i in keep],
        "tombstones": [
            {"listing_id": r["listing"]["id"], "source_id": r["source"]["id"], "reason": "ineligible"}
            for i, r in enumerate(records)
            if i not in keep
        ],
    }


async def test_removed_member_and_all_removed_never_remain_visible_and_can_restore(seed_database):
    engine, factory, state, original, health, incoming = await setup(seed_database)
    try:
        await refresh(factory, original, incoming, health=health)
        assert (await CatalogReadiness(pipeline(factory), health)())["catalog_ready"]
        await assert_visible(factory, health, 3)
        await refresh(factory, original, envelope(original, [1, 2]), health=health)
        async with factory() as session:
            cards = (await session.scalars(select(Listing).order_by(Listing.id))).all()
            assert [r.status for r in cards] == ["draft", "published", "published"]
            assert await session.scalar(text("SELECT count(*) FROM ai_query_proofs")) == 2
        await assert_visible(factory, health, 2)
        await refresh(factory, original, envelope(original, []), health=health)
        assert not (await CatalogReadiness(pipeline(factory), health)())["catalog_ready"]
        await assert_visible(factory, health, 0)
        async with factory() as session:
            assert await session.scalar(text("SELECT count(*) FROM listings WHERE status='published'")) == 0
        await refresh(factory, original, envelope(original), health=health)
        assert (await CatalogReadiness(pipeline(factory), health)())["catalog_ready"]
        await assert_visible(factory, health, 3)
        assert PilotBudget(state / "provider.sqlite3").summary()["attempts"] == 0
    finally:
        await engine.dispose()


async def test_incomplete_untrusted_receipt_blocks_all_until_full_reconcile(seed_database):
    engine, factory, state, original, health, incoming = await setup(seed_database)
    try:
        await refresh(factory, original, incoming, health=health)
        for kind in ["missing", "unknown", "duplicate", "future", "stale","source_fields"]:
            bad = copy.deepcopy(incoming)
            if kind == "missing":
                bad["records"].pop()
            if kind == "unknown":
                bad["cohort"][0]["listing_id"] = "00000000-0000-4000-8000-000000000099"
            if kind == "duplicate":
                bad["tombstones"] = [
                    {
                        "listing_id": bad["records"][0]["listing"]["id"],
                        "source_id": bad["records"][0]["source"]["id"],
                        "reason": "ineligible",
                    }
                ] * 2
            if kind == "future":
                bad["snapshot_at"] = "2099-01-01T00:00:00Z"
            if kind == "stale":
                bad["records"][0]["source"]["last_success_at"] = "2020-01-01T00:00:00Z"
            if kind=='source_fields':bad['records'][0]['source']['normalized_payload']['contact']='PRIVATE_CANARY'
            with pytest.raises(ValueError):
                await refresh(factory, original, bad, health=health)
            assert not (await CatalogReadiness(pipeline(factory), health)())["catalog_ready"]
            with pytest.raises(SourceCoverageUnavailable):
                await assert_visible(factory, health, 3)
            await refresh(factory, original, incoming, health=health)
            await assert_visible(factory, health, 3)
        assert PilotBudget(state / "provider.sqlite3").summary()["attempts"] == 0
    finally:
        await engine.dispose()


async def test_exhausted_fact_job_reconciles_new_work_generation_without_resetting_history(seed_database):
    engine, factory, _, original, health, incoming = await setup(seed_database)
    try:
        observed = incoming["records"][0]["source"]["last_success_at"]

        async def fault(phase, index):
            if phase == "claimed" and index == 0:
                raise RuntimeError("SYNTHETIC_CLAIM_FAILURE")

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await refresh(factory, original, incoming, health=health, checkpoint=fault)
        async with factory() as session:
            failed_before = (
                await session.execute(text("SELECT id,attempts,fence FROM ai_fact_jobs WHERE status='failed'"))
            ).all()
            assert len(failed_before) == 1 and failed_before[0].attempts == 2
        await refresh(factory, original, incoming, health=health)
        await assert_visible(factory, health, 3)
        async with factory() as session:
            assert (
                await session.execute(text("SELECT id,attempts,fence FROM ai_fact_jobs WHERE status='failed'"))
            ).all() == failed_before
            source_time = await session.scalar(
                text("SELECT last_success_at FROM external_listing_sources WHERE id=:id"),
                {"id": UUID(incoming["records"][0]["source"]["id"])},
            )
            assert source_time == datetime.fromisoformat(observed)
    finally:
        await engine.dispose()


@pytest.mark.parametrize("phase", ["source_commit", "observe", "claimed", "complete", "proof"])
async def test_partial_refresh_is_unreadable_until_complete_rerun(seed_database, phase):
    engine, factory, state, original, health, incoming = await setup(seed_database)
    try:
        await refresh(factory, original, incoming, health=health)
        old = health.ticket()

        async def fail(name, index):
            if name == phase and (index == 1 or name == "source_commit"):
                assert not (await CatalogReadiness(pipeline(factory), health)())["catalog_ready"]
                with pytest.raises(SourceCoverageUnavailable):
                    GuardedCards.ticket(type("Guard", (), {"health": health})())
                raise RuntimeError("SYNTHETIC_REFRESH_FAULT")

        changed = envelope(original)
        for r in changed["records"]:
            r["listing"]["pets_allowed"] = True
        with pytest.raises(RuntimeError, match="SYNTHETIC_REFRESH_FAULT"):
            await refresh(factory, original, changed, health=health, checkpoint=fail)
        assert not (await CatalogReadiness(pipeline(factory), health)())["catalog_ready"]
        with pytest.raises(ValueError):
            health.ticket()
        await refresh(factory, original, changed, health=health)
        assert health.ticket() != old and (await CatalogReadiness(pipeline(factory), health)())["catalog_ready"]
        async with factory() as session:
            assert (await session.scalars(select(Listing.pets_allowed))).all() == [True] * 3
            assert await session.scalar(text("SELECT coalesce(sum(used+reserved),0) FROM ai_usage_days")) == 0
        assert PilotBudget(state / "provider.sqlite3").summary()["attempts"] == 0
    finally:
        await engine.dispose()


async def test_all_whitelisted_public_fields_and_price_follow_receipt(seed_database):
    engine, factory, _state, original, health, incoming = await setup(seed_database)
    try:
        r = incoming["records"][0]
        r["listing"].update(
            pets_allowed=True,
            furnished=False,
            amenities=["desk"],
            latitude=28.42,
            longitude=-16.2,
            monthly_price=710,
            source_price_text="710 €/mes",
        )
        r["source"].update(source_price_text="710 €/mes")
        r["source"]["normalized_payload"].update(price_amount=710, source_price_text="710 €/mes")
        await refresh(factory, original, incoming, health=health)
        async with factory() as session:
            card = await session.get(Listing, UUID(r["listing"]["id"]))
            assert card.pets_allowed and not card.furnished and card.amenities == ["desk"] and card.monthly_price == 710
            assert (
                round(
                    await session.scalar(
                        text("SELECT ST_Y(location::geometry) FROM listings WHERE id=:id"), {"id": card.id}
                    ),
                    2,
                )
                == 28.42
            )
    finally:
        await engine.dispose()


@pytest.mark.parametrize("mutation", ["deleted", "unpublished", "inactive", "stale", "inconsistent_price","all_gone"])
async def test_producer_emits_exact_tombstone_for_ineligible_source(seed_database, mutation):
    engine, factory, _, original, _, _ = await setup(seed_database)
    try:
        spec = importlib.util.spec_from_file_location(
            "public_export", Path(__file__).parents[3] / "deploy/ai-text-demo/export_public.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        lid = UUID(original["records"][0]["listing"]["id"])
        sid = UUID(original["records"][0]["source"]["id"])
        statements = {
            "all_gone":"UPDATE listings SET status='hidden'",
            "deleted": "UPDATE listings SET deleted_at=now() WHERE id=:id",
            "unpublished": "UPDATE listings SET status='hidden' WHERE id=:id",
            "inactive": "UPDATE external_listing_sources SET current_status='inactive' WHERE id=:id",
            "stale": "UPDATE external_listing_sources SET last_success_at=now()-interval '25 hours' WHERE id=:id",
            "inconsistent_price": "UPDATE listings SET monthly_price=999 WHERE id=:id",
        }
        async with factory.begin() as session:
            await session.execute(text(statements[mutation]), {"id": sid if mutation in {"inactive", "stale"} else lid})
        async with factory() as session:
            value = await session.scalar(text(module.snapshot_statement(original)))
        if isinstance(value, str):
            value = json.loads(value)
        if mutation=='all_gone':
            assert len(value['cohort'])==3 and value['records']==[] and len(value['tombstones'])==3
            return
        assert (
            len(value["cohort"]) == 3
            and len(value["records"]) == 2
            and value["tombstones"] == [{"listing_id": str(lid), "source_id": str(sid), "reason": "ineligible"}]
        )
    finally:
        await engine.dispose()
