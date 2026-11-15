"""Primary imported source -> facts/proof -> current saved matcher, no provider."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import update
from test_ai_verified_cards import setup

from app.db.session import SessionLocal
from app.models import ExternalListingSource, Listing
from app.repositories.ai_verified_cards import verified_intent_predicate
from app.repositories.listings import visible_query
from app.schemas.ai_search_intent import Criteria, Criterion, SearchIntent
from app.services.ai_housing_catalog import housing_pipeline
from app.services.ai_saved_catalog import refresh_saved_catalog

pytestmark = pytest.mark.integration


async def test_original_import_cas_freshness_and_fact_query_without_source_rewrite():
    _, _, _, ids, sources = await setup("long", price=600)
    source_id, listing_id = sources[1], ids[1]
    now = datetime.now(UTC)
    normalized = {"source_name": "PisoCompartido", "source_price_text": "600 €/mes", "rental_mode": "long",
        "price_currency": "EUR", "price_period": "month", "price_is_from": False, "price_amount": 600,
        "city": "Madrid", "title": "Habitación amueblada", "description": "Gastos incluidos."}
    raw = {"html": '<div class="seccionesFichaAnuncio"><div class="contCaract"><li>Wifi</li></div></div>'}
    async with SessionLocal.begin() as conn:
        await conn.execute(update(ExternalListingSource).where(ExternalListingSource.id == source_id).values(
            source_name="PisoCompartido", source_url="https://www.pisocompartido.com/habitacion/123456/",
            normalized_payload=normalized, raw_payload=raw, source_price_text="600 €/mes", last_success_at=now))
    pipeline = housing_pipeline(SessionLocal, resolver_version="housing-main.v1")
    result = await refresh_saved_catalog(pipeline, (source_id,))
    assert result == {"sources": 1, "proofs_prepared": 1, "rejected": 0, "provider_calls": 0, "source_updates": 0}
    criteria = Criteria.model_validate({"budget": {"strength": "hard", "value": {"amount": "600", "currency": "EUR", "period": "monthly"}},
        "furnished": {"strength": "hard", "value": True}, "bills_included": {"strength": "hard", "value": True},
        "geography": {"strength": "hard", "value": {"province_code": "28", "municipality_code": "28079"}}})
    intent = SearchIntent(schema_version="ai-search.v1", taxonomy_version="rental.v1", session_id=uuid4(), version=0, criteria=criteria)

    async def matches():
        async with SessionLocal() as conn:
            return list(await conn.scalars(visible_query().where(verified_intent_predicate(pipeline, intent)).with_only_columns(Listing.id)))

    assert await matches() == [listing_id]
    async with SessionLocal() as conn:
        unchanged = await conn.get(ExternalListingSource, source_id)
        assert unchanged.raw_payload == raw and unchanged.normalized_payload == normalized and unchanged.last_success_at == now
    async with SessionLocal.begin() as conn:
        await conn.execute(update(ExternalListingSource).where(ExternalListingSource.id == source_id).values(
            normalized_payload=normalized | {"description": "Gastos no incluidos."}))
    assert await matches() == []  # Original snapshot proof cannot survive changed input.
    assert (await refresh_saved_catalog(pipeline, (source_id,)))["proofs_prepared"] == 1
    assert await matches() == []
    intent = intent.model_copy(update={"criteria": criteria.model_copy(update={"bills_included": Criterion(strength="hard", value=False)})})
    assert await matches() == [listing_id]
    async with SessionLocal.begin() as conn:
        await conn.execute(update(ExternalListingSource).where(ExternalListingSource.id == source_id).values(
            last_success_at=now - timedelta(days=2)))
    assert (await refresh_saved_catalog(pipeline, (source_id,)))["proofs_prepared"] == 1
    assert await matches() == []  # Recapture cannot renew the source freshness clock.
