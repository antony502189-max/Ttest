"""Actual refresh failures through owned-session cards/map and manual search.

Uses the complete historical migration chain in its own disposable schema,
not the minimal legacy stand-ins of the other facts fixtures.
"""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import ExternalListingSource, Listing, User
from app.models.ai_search_session import AISearchSession
from app.repositories.ai_fact_pipeline import FactPipeline
from app.repositories.ai_query_proofs import QueryProofs
from app.repositories.ai_search_quota import QuotaLedger
from app.repositories.ai_search_sessions import IntentVocabulary, SearchSessions, SessionPolicy
from app.repositories.ai_verified_cards import VerifiedCardSearch
from app.repositories.listings import point, search_public_cards
from app.schemas.ai_fact_bridge import BridgeMapping, ParserEvidencePacket
from app.schemas.ai_fact_pipeline import FactQueuePolicy
from app.schemas.ai_listing_facts import FactVocabulary
from app.schemas.ai_search_quota import LeasePolicy, QuotaSubject
from app.schemas.listings import ListingCardSearchRequest, ListingMapRequest
from app.services.ai_fact_coordinator import OfflineFactCoordinator, SourceFactPolicy
from app.services.ai_fact_quality import FactQualityPolicy
from lab.ai_fact_refresh import SyntheticDetailRefresh, SyntheticRefreshPolicy
from lab.ai_fact_supervisor import (
    SupervisorPolicy,
    SyntheticFactSupervisor,
    SyntheticSupervisorJournal,
    configuration_digest,
)

pytestmark = pytest.mark.integration
CASES = json.loads((Path(__file__).parents[1] / "fixtures/ai_fact_bridge/parser-373-synthetic.json").read_text(encoding="utf-8"))
BUNDLE = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


@pytest_asyncio.fixture
async def full_sessions(pg):
    # pg already enforces explicit owned disposable loopback DB selection.
    sync_engine = pg[0]
    schema = "ai_facts_" + uuid4().hex
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parents[2] / "alembic"))
    revisions = list(reversed(list(ScriptDirectory.from_config(config).walk_revisions())))
    engine = None
    try:
        with sync_engine.connect() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET search_path TO "{schema}", public'))
            connection.commit()
            context = MigrationContext.configure(connection, opts={"transaction_per_migration": True})
            with Operations.context(context):
                for revision in revisions:
                    with context.begin_transaction(_per_migration=True):
                        revision.module.upgrade()
            connection.execute(text("RESET search_path"))
            connection.commit()
        engine = create_async_engine(sync_engine.url.set(drivername="postgresql+asyncpg"), connect_args={
            "server_settings": {"search_path": f"{schema},public", "lock_timeout": "5000", "statement_timeout": "10000"}})
        yield async_sessionmaker(engine, expire_on_commit=False), schema
    finally:
        if engine is not None:
            await engine.dispose()
        with sync_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


def builder(snapshot):
    data = json.loads(snapshot.normalized_json)["packet"]
    data.update(source_identifier=snapshot.reference.source_identifier,
                canonical_listing_identifier=str(snapshot.reference.canonical_listing_id))
    return ParserEvidencePacket.model_validate_json(json.dumps(data))


@pytest.mark.parametrize("status", [403, 429, None, 200])
async def test_new_refresh_failure_filters_cards_map_count_before_limit_and_preserves_manual(full_sessions, tmp_path, status):
    sessions, schema = full_sessions
    vocabulary = FactVocabulary(amenity_codes=frozenset(), catalog_other_codes=frozenset(),
                                tenant_group_codes=frozenset(), municipality_zones=frozenset())
    pipeline = FactPipeline(sessions, FactQueuePolicy(lease_seconds=60, max_attempts=2, retry_delay_seconds=1),
        vocabulary, resolver_version="review-refresh.v1", operating_policy=FactQualityPolicy(
            price_max_age_seconds=86400, policy_max_age_seconds=86400, evidence_retention_seconds=604800))
    ledger = QuotaLedger(sessions, LeasePolicy(reservation_seconds=60, running_seconds=60, recovery_grace_seconds=30))
    owned_sessions = SearchSessions(ledger, SessionPolicy(inactivity_seconds=600), IntentVocabulary(
        vocabulary.amenity_codes, vocabulary.catalog_other_codes, vocabulary.municipality_zones))
    subject = QuotaSubject(kind="guest", id=uuid4())
    owned = await owned_sessions.create(subject)
    cohort = []
    async with sessions() as session, session.begin():
        await session.execute(update(AISearchSession).where(AISearchSession.id == owned.intent.session_id).values(
            version=1, criteria={"pets": {"strength": "hard", "value": [{"species": "dog", "size": "small", "count": 1}]}}))
        owner = User(email="refresh-cards@example.invalid", password_hash="unused", name="Synthetic Host",
                     role="host", initials="SH", email_verified=True)
        session.add(owner)
        await session.flush()
        for index in range(4):
            listing = Listing(owner_user_id=owner.id, title=f"Synthetic {index}", city="Adeje", area="Adeje",
                approximate_address="Synthetic address", rental_mode="long", monthly_price=700,
                location=point(-16.733, 28.061), status="published", published_at=datetime.now(UTC), is_external=True,
                external_image_urls=[f"https://images.invalid/{index}/{i}.jpg" for i in range(5)])
            session.add(listing)
            await session.flush()
            packet = next(c["packet"] for c in CASES["cases"] if c["name"] == ("pets_deny" if index == 0 else "pets_allow"))
            source = ExternalListingSource(source_name="synthetic", external_id=str(index),
                source_url=f"https://example.invalid/{index}", canonical_listing_id=listing.id,
                fingerprint=hashlib.sha256(str(index).encode()).hexdigest(), current_status="active",
                raw_payload={}, normalized_payload={"packet": packet}, last_success_at=datetime.now(UTC) - timedelta(seconds=61))
            session.add(source)
            await session.flush()
            cohort.append((source.id, listing.id))
    mapping = BridgeMapping(structured_fields={}, rented_unit_capacity_fields=frozenset(), text_capacity_scope=None,
        structured_smoking_scopes={}, text_smoking_scopes={}, amenity_codes={})
    coordinator = OfflineFactCoordinator(pipeline, sources=(SourceFactPolicy("synthetic", mapping, builder,
        "review-refresh.v1", 60, 4, False),), max_sources=4, max_reconcile=4, max_payload_bytes=131_072)
    catalog = hashlib.sha256(schema.encode()).hexdigest()
    journal = SyntheticSupervisorJournal(tmp_path / "DISPOSABLE-fact-supervisor-cards.sqlite3",
        configuration_sha256=configuration_digest(coordinator, builder_bundle_sha256=BUNDLE, catalog_identity_sha256=catalog),
        policy=SupervisorPolicy(10, 10, 20, 2, 8, 60, 10, 100))
    supervisor = SyntheticFactSupervisor(coordinator, journal, builder_bundle_sha256=BUNDLE, catalog_identity_sha256=catalog)
    assert await supervisor.run_once() == "committed"
    query = VerifiedCardSearch(pipeline, owned_sessions, signing_key=b"synthetic-cards-review-key-32bytes")
    cards = ListingCardSearchRequest(limit=1)
    viewport = ListingMapRequest(west=-17, south=28, east=-16, north=29, zoom=14)
    async with sessions() as session:
        assert (await search_public_cards(session, cards)).total == 4
    assert journal.receipt(1)["observed"] == 4 and journal.receipt(1)["proofs_prepared"] == 4
    assert (await query.search_owned(subject, owned.intent.session_id, 1, cards)).cards.total == 3
    assert len((await query.map_owned(subject, owned.intent.session_id, 1, viewport)).map.items) == 3
    async with sessions() as session:
        assert (await search_public_cards(session, cards)).total == 4
    calls = []

    def response(request):
        calls.append(request)
        if status is None:
            raise httpx.ReadTimeout("synthetic timeout", request=request)
        return httpx.Response(status, json={"invalid": "detail"})

    consumer = SyntheticDetailRefresh(supervisor, policy=SyntheticRefreshPolicy(
        "synthetic", "example.invalid", 4, 131_072, 1, 10), cohort=tuple(cohort),
        transport=httpx.MockTransport(response), mock_bundle_sha256=BUNDLE)
    await consumer.initialize()
    result = await consumer.run_receipt(1, expected_digest=journal.receipt_digest(1))
    assert result.outcomes == ("failed",) * 4 and len(calls) == 4 and not result.acknowledged
    # Repreparing proofs cannot turn the failed current check into healthy AI data.
    for _, listing in cohort:
        await QueryProofs(pipeline).prepare(listing)
    found = (await query.search_owned(subject, owned.intent.session_id, 1, cards)).cards
    assert found.total == 0 and not found.items
    assert not (await query.map_owned(subject, owned.intent.session_id, 1, viewport)).map.items
    async with sessions() as session:
        assert (await search_public_cards(session, cards)).total == 4
        assert await session.scalar(select(func.count()).select_from(ExternalListingSource).where(
            ExternalListingSource.current_status == "active")) == 4
    assert journal.pending().refresh == 4
