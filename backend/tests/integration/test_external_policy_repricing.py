from dataclasses import replace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from test_external_import_lifecycle import external_item

from app.db.session import SessionLocal
from app.models import ExternalListingSource, Listing
from app.repositories.listings import visible_query
from app.services import external_import

pytestmark = pytest.mark.integration


async def test_repricing_withdraws_then_restores_same_identity_without_invalid_media(monkeypatch):
    fingerprints = AsyncMock(return_value=[])
    monkeypatch.setattr(external_import, "public_image_fingerprints", fingerprints)
    item = external_item(source="Pisos", external_id="price-policy", url="https://www.pisos.com/alquilar/policy-123456/", price=850)
    async with SessionLocal() as session:
        assert await external_import.upsert(session, item) == "imported"
        source = await session.scalar(select(ExternalListingSource))
        listing_id = source.canonical_listing_id
        await session.commit()
        fingerprints.reset_mock()
        expensive = replace(item, price_amount=1250, source_price_text="1250 €/mes", photos=["https://images.example.test/a.jpg"])
        assert await external_import.upsert(session, expensive) == "policy_rejected"
        assert await external_import.upsert(session, expensive) == "policy_rejected"
        fingerprints.assert_not_awaited()
        assert not (await session.execute(visible_query())).all()
        await session.commit()
        assert await external_import.upsert(session, replace(item, price_amount=900, source_price_text="900 €/mes")) in {"restored", "updated"}
        sources = list((await session.scalars(select(ExternalListingSource))).all())
        assert len(sources) == 1 and sources[0].canonical_listing_id == listing_id
        assert await session.scalar(select(func.count()).select_from(Listing)) == 1
        assert (await session.get(Listing, listing_id)).monthly_price == 900
        assert len((await session.execute(visible_query())).all()) == 1


@pytest.mark.parametrize("changes", [{"rental_mode": "holiday", "price_period": "night"},
    {"price_period": None}, {"price_currency": "USD"}, {"price_is_from": True}, {"price_amount": 1001}])
async def test_final_persistence_guard_rejects_adapter_bugs(changes, monkeypatch):
    fingerprints = AsyncMock(return_value=[])
    monkeypatch.setattr(external_import, "public_image_fingerprints", fingerprints)
    item = external_item(source="Pisos", external_id="invalid", url="https://www.pisos.com/alquilar/invalid-123456/")
    async with SessionLocal() as session:
        assert await external_import.upsert(session, replace(item, **changes)) == "policy_rejected"
        assert await session.scalar(select(func.count()).select_from(Listing)) == 0
        fingerprints.assert_not_awaited()
