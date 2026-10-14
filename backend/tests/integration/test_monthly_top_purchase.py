from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select

from test_banner_payment_lifecycle import provider, webhook
from test_homepage_purchase import listing
from app.db.session import SessionLocal
from app.models import Listing
from app.models.moderation import ListingPromotion
from app.models.payment_order import PaymentOrder
from app.services.homepage_purchase import one_month_after

pytestmark = pytest.mark.integration


async def purchase(client, provider, target, headers):
    response = await client.post(f'/api/v1/payments/listings/{target}/top/checkout', headers=headers,
                                 json={'days': 30, 'amountCents': 1, 'currency': 'usd'})
    assert response.status_code == 200, response.text
    assert response.json()['amountCents'] == 3000
    return response, provider[response.json()['url'].rsplit('/', 1)[-1]]


async def test_monthly_top_payment_priority_renewal_and_expiry(client, register_user, provider):
    target, headers = await listing(client, register_user, 'monthly-top@example.com')
    regular, _ = await listing(client, register_user, 'ordinary-top@example.com')
    async with SessionLocal() as db:
        old = await db.get(Listing, UUID(target))
        old.created_at = datetime.now(UTC) - timedelta(days=10)
        old.monthly_price = 990
        await db.commit()
    response, remote = await purchase(client, provider, target, headers)
    repeat, _ = await purchase(client, provider, target, headers)
    assert repeat.json()['url'] == response.json()['url'] and len(provider) == 1
    before = await client.post('/api/v1/listings/search', json={'rentalMode':'long'})
    assert before.json()['items'][0]['id'] == regular
    remote.update(status='complete', payment_status='paid')
    assert (await webhook(client, remote)).status_code == 200
    assert (await webhook(client, remote)).status_code == 200
    async with SessionLocal() as db:
        promotion = await db.get(ListingPromotion, UUID(target))
        original_end = promotion.ends_at
        original_boost = promotion.boosted_at
        assert original_end == one_month_after(promotion.starts_at)
        order = await db.scalar(select(PaymentOrder).where(PaymentOrder.target_id == UUID(target)))
        assert order.duration_months == 1 and order.status == 'paid' and order.fulfillment_status == 'fulfilled'
    for sort in ['newest', 'oldest', 'price_asc', 'price_desc']:
        result = await client.post('/api/v1/listings/search', json={'rentalMode':'long','sort':sort})
        assert result.status_code == 200, result.text
        assert result.json()['items'][0]['id'] == target and result.json()['items'][0]['promoted']
    _, renewal = await purchase(client, provider, target, headers)
    renewal.update(status='complete', payment_status='paid')
    # Authenticated GET recovery must activate the service without a webhook.
    status = await client.get(f'/api/v1/payments/listings/{target}/top/status', headers=headers)
    assert status.json()['fulfillmentStatus'] == 'fulfilled'
    async with SessionLocal() as db:
        promotion = await db.get(ListingPromotion, UUID(target))
        assert promotion.ends_at == one_month_after(original_end)
        assert promotion.boosted_at > original_boost
        assert promotion.total_price_cents == 6000
        promotion.ends_at = datetime.now(UTC) - timedelta(seconds=1)
        await db.commit()
    result = await client.post('/api/v1/listings/search', json={'rentalMode':'long'})
    assert result.json()['items'][0]['id'] == regular
    assert not next(item for item in result.json()['items'] if item['id'] == target)['promoted']


async def test_monthly_top_rejects_old_packages_and_unauthorized_purchase(client, register_user, provider):
    target, headers = await listing(client, register_user, 'monthly-owner@example.com')
    _, stranger = await listing(client, register_user, 'monthly-stranger@example.com')
    route = f'/api/v1/payments/listings/{target}/top/checkout'
    for days in [1, 7, 29, 31, 30.5, '30', True]:
        assert (await client.post(route, headers=headers, json={'days':days})).status_code == 422
    assert (await client.post(route, headers=stranger, json={'days':30})).status_code == 404
    assert not provider
    await purchase(client, provider, target, headers)
    cancelled = await client.post(route + '/cancel', headers=headers)
    assert cancelled.json()['cancelled']
    state = await client.get(f'/api/v1/payments/listings/{target}/top/status', headers=headers)
    assert state.json()['orderStatus'] == 'expired' and state.json()['endsAt'] is None
