from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
import test_banner_payment_lifecycle as payment_lifecycle
from sqlalchemy import select
from test_banner_payment_lifecycle import webhook
from test_homepage_purchase import listing

from app.db.session import SessionLocal
from app.models import Listing, ListingImage
from app.models.moderation import ListingPromotion
from app.models.payment_order import PaymentOrder

provider = payment_lifecycle.provider

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
        assert original_end == promotion.starts_at + timedelta(days=30)
        order = await db.scalar(select(PaymentOrder).where(PaymentOrder.target_id == UUID(target)))
        assert order.duration_months is None and order.days == 30 and order.status == 'paid' and order.fulfillment_status == 'fulfilled'
        assert promotion.daily_price_cents == 100
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
        assert promotion.ends_at == original_end + timedelta(days=30)
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
    for days in [1, 7, 9, 366, 30.5, '30', True]:
        assert (await client.post(route, headers=headers, json={'days':days})).status_code == 422
    assert (await client.post(route, headers=stranger, json={'days':30})).status_code == 404
    assert not provider
    await purchase(client, provider, target, headers)
    cancelled = await client.post(route + '/cancel', headers=headers)
    assert cancelled.json()['cancelled']
    state = await client.get(f'/api/v1/payments/listings/{target}/top/status', headers=headers)
    assert state.json()['orderStatus'] == 'expired' and state.json()['endsAt'] is None


async def test_top_selected_listing_duration_and_server_price(client, register_user, provider):
    first, headers = await listing(client, register_user, 'chosen-top@example.com')
    # Make a second eligible listing owned by the same user.
    async with SessionLocal() as db:
        source = await db.get(Listing, UUID(first))
        fields = {col.name: getattr(source, col.name) for col in Listing.__table__.columns
                  if col.name not in {'id', 'created_at', 'updated_at'}}
        fields['title'] = 'Second chosen listing'
        fields['location'] = 'SRID=4326;POINT(-16.7260 28.0902)'
        fields['exact_location'] = None
        second = Listing(**fields)
        db.add(second)
        await db.flush()
        images = (await db.scalars(select(ListingImage).where(ListingImage.listing_id == source.id))).all()
        for image in images:
            db.add(ListingImage(listing_id=second.id, media_asset_id=image.media_asset_id,
                                sort_order=image.sort_order, is_cover=image.is_cover))
        await db.commit()
        second_id = str(second.id)
    response = await client.post(f'/api/v1/payments/listings/{second_id}/top/checkout', headers=headers,
                                 json={'days':21, 'amountCents':1})
    assert response.status_code == 200 and response.json()['amountCents'] == 2100
    remote = provider[response.json()['url'].rsplit('/', 1)[-1]]
    remote.update(status='complete', payment_status='paid')
    assert (await webhook(client, remote)).status_code == 200
    async with SessionLocal() as db:
        assert await db.get(ListingPromotion, UUID(first)) is None
        promotion = await db.get(ListingPromotion, UUID(second_id))
        assert promotion.ends_at - promotion.starts_at == timedelta(days=21)
