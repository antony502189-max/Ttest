from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from app.models.moderation import ListingPromotion
from app.models import Listing
from app.models.payment_order import PaymentOrder
from app.schemas.listings import ListingSearchRequest
from app.services.province_top import next_available, require_top_address_mutable, top_availability
from app.spain_provinces import PROVINCE_CODES, address_province_code, province_code_expression

NOW = datetime(2026, 10, 17, tzinfo=UTC)


def test_full_province_waits_for_earliest_expiry_and_allows_exact_boundary():
    windows = [(str(i), NOW - timedelta(days=1), NOW + timedelta(hours=i)) for i in (1, 2, 3)]
    assert next_available(windows, NOW, NOW + timedelta(days=10)) == NOW + timedelta(hours=1)
    assert next_available(windows, NOW + timedelta(hours=1), NOW + timedelta(days=10)) == NOW + timedelta(hours=1)


def test_renewal_reservation_counts_one_listing_and_missing_confirmation_never_releases_it():
    windows = [(str(i), NOW, None) for i in (1, 2, 3)]
    windows.append(('1', NOW, NOW + timedelta(hours=1)))
    assert next_available(windows, NOW, NOW + timedelta(days=10)) is None
    assert next_available(windows[:2], NOW, NOW + timedelta(days=10)) == NOW


def test_scheduled_top_blocks_overlapping_purchase_but_not_adjacent_interval():
    windows = [(str(i), NOW + timedelta(days=5), NOW + timedelta(days=15)) for i in (1, 2, 3)]
    assert next_available(windows, NOW, NOW + timedelta(days=10)) == NOW + timedelta(days=15)
    assert next_available(windows, NOW, NOW + timedelta(days=5)) == NOW


def test_more_than_three_legacy_promotions_wait_until_count_drops_below_three():
    windows = [(str(i), NOW, NOW + timedelta(hours=i)) for i in range(1, 6)]
    assert next_available(windows, NOW, NOW + timedelta(days=10)) == NOW + timedelta(hours=3)


@pytest.mark.parametrize(('postcode', 'expected'), [('28013', '28'), ('08001', '08'), ('38001', '38'),
    ('35001', '35'), ('01001', '01'), ('51001', '51'), ('52001', '52'), (' 29001 ', '29'),
    ('53001', None), ('00000', None), ('2801', None), ('', None), (None, None), ('２８０１３', None)])
def test_address_province(postcode, expected):
    assert address_province_code(postcode) == expected


def test_province_search_is_validated_and_does_not_expose_private_postcodes():
    assert len(PROVINCE_CODES) == 52
    assert ListingSearchRequest(provinceCode='28').provinceCode == '28'
    with pytest.raises(ValueError):
        ListingSearchRequest(provinceCode='53')
    sql = str(province_code_expression().compile(dialect=postgresql.dialect()))
    assert 'substr' in sql and 'postcode' in sql


class Session:
    def __init__(self, promotions=(), reservations=(), own=None):
        self.promotions, self.reservations, self.own = promotions, reservations, own
        self.queries = []

    async def get(self, model, key):
        return self.own if model is ListingPromotion else None

    async def execute(self, statement):
        self.queries.append(statement)
        return SimpleNamespace(all=lambda: self.promotions)

    async def scalars(self, statement):
        self.queries.append(statement)
        return SimpleNamespace(all=lambda: self.reservations)

    async def scalar(self, statement):
        return self.reservations[0] if self.reservations else None


@pytest.mark.asyncio
async def test_availability_filters_both_promotions_and_pending_orders_by_same_province():
    listing = SimpleNamespace(id=uuid4(), postcode='28013')
    session = Session()
    result = await top_availability(session, listing)
    assert result['available'] and result['provinceCode'] == '28' and result['province'] == 'Madrid'
    for statement in session.queries:
        compiled = statement.compile(dialect=postgresql.dialect())
        assert 'postcode' in str(compiled)
        assert '28' in compiled.params.values()


@pytest.mark.asyncio
async def test_unresolved_reservations_fill_province_without_fake_release_time():
    listing = SimpleNamespace(id=uuid4(), postcode='28013')
    result = await top_availability(Session(reservations=[uuid4() for _ in range(3)]), listing)
    assert result['available'] is False and result['availableAt'] is None and result['availableSlots'] == 0


@pytest.mark.asyncio
async def test_missing_postcode_cannot_buy_unscoped_top():
    with pytest.raises(HTTPException) as error:
        await top_availability(Session(), SimpleNamespace(id=uuid4(), postcode=''))
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_active_or_pending_top_cannot_move_to_another_province():
    listing = SimpleNamespace(id=uuid4(), postcode='28013')
    for session in [Session(own=SimpleNamespace(ends_at=None)), Session(reservations=[uuid4()])]:
        await require_top_address_mutable(session, listing, '28001')
        with pytest.raises(HTTPException) as error:
            await require_top_address_mutable(session, listing, '08001')
        assert error.value.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize('peer_count', [2, 3])
async def test_financial_restoration_obeys_province_capacity(monkeypatch, peer_count):
    from app.services import payment_finances
    now = datetime.now(UTC)
    listing = SimpleNamespace(id=uuid4(), postcode='28013')
    promotion = SimpleNamespace(payment_managed=True, baseline_starts_at=None, baseline_ends_at=None,
                                starts_at=now - timedelta(days=1), ends_at=now - timedelta(seconds=1))
    order = SimpleNamespace(kind='listing_top', id=uuid4(), target_id=listing.id, financial_status='normal',
                            fulfillment_status='review_required', service_starts_at=now,
                            service_ends_at=now + timedelta(days=10), paid_at=now, amount_cents=1000)

    class FinancialSession(Session):
        async def get(self, model, key):
            return listing if model is Listing else promotion

        async def scalars(self, statement):
            entity = statement.column_descriptions[0]['expr']
            rows = [order] if entity is PaymentOrder and order.fulfillment_status == 'fulfilled' else []
            return SimpleNamespace(all=lambda: rows)

    session = FinancialSession(promotions=[(uuid4(), now - timedelta(days=1), now + timedelta(days=20))
                                           for _ in range(peer_count)])
    monkeypatch.setattr(payment_finances, 'touch_catalog', AsyncMock())
    await payment_finances.change_service_finances(order, session)
    assert order.fulfillment_status == ('fulfilled' if peer_count == 2 else 'review_required')
    assert (promotion.ends_at > now) == (peer_count == 2)
