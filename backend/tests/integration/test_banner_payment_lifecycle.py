"""Real PostgreSQL transactions, signed events, seven-slot capacity and recovery."""
import asyncio
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import func, select
from test_commercial_advertisements import admin_headers, create_ad

from app.api.v1 import payments
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Notification
from app.models.commercial_advertisement import CommercialAdvertisement
from app.models.payment_order import PaymentOrder
from app.services import advertising_alerts, payment_fulfillment, stripe_checkout

pytestmark = pytest.mark.integration


@pytest.fixture
def provider(monkeypatch):
    remote = {}
    settings = get_settings().model_copy(update={'stripe_secret_key': 'sk_test_review', 'stripe_webhook_secret': 'whsec_review'})
    for module in (payments, stripe_checkout, payment_fulfillment):
        monkeypatch.setattr(module, 'get_settings', lambda: settings)

    async def create(order, *_):
        key = 'cs_test_' + str(order.id)
        remote[key] = {'id': key, 'client_reference_id': str(order.id), 'status': 'open', 'payment_status': 'unpaid',
                       'amount_total': order.amount_cents, 'currency': 'eur', 'livemode': False}
        return key, 'https://checkout.stripe.com/' + key

    async def retrieve(key):
        return dict(remote[key])

    async def expire(key):
        if remote[key]['status'] != 'complete':
            remote[key]['status'] = 'expired'
        return dict(remote[key])

    monkeypatch.setattr(payments, 'create_stripe_session', create)
    monkeypatch.setattr(payments, 'retrieve_stripe_session', retrieve)
    monkeypatch.setattr(payments, 'expire_stripe_session', expire)
    monkeypatch.setattr(advertising_alerts, 'retrieve_stripe_session', retrieve)
    return remote


async def checkout(client, ad, headers):
    return await client.post('/api/v1/payments/advertisements/' + ad['id'] + '/checkout', headers=headers)


async def webhook(client, remote, event='checkout.session.completed'):
    body = json.dumps({'type': event, 'data': {'object': remote}}).encode()
    stamp = int(time.time())
    signature = hmac.new(b'whsec_review', str(stamp).encode() + b'.' + body, hashlib.sha256).hexdigest()
    return await client.post('/api/v1/payments/stripe/webhook', content=body,
                             headers={'Stripe-Signature': f't={stamp},v1={signature}', 'Content-Type': 'application/json'})


async def paid(client, provider, url):
    remote = provider[url.rsplit('/', 1)[-1]]
    remote.update(status='complete', payment_status='paid')
    response = await webhook(client, remote)
    assert response.status_code == 200, response.text
    return remote


async def campaigns_from_distinct_clients(client, register_user, prefix):
    # Eight independent advertisers must not share one synthetic ASGI peer/IP.
    original = client._transport.client
    result = []
    try:
        for index in range(8):
            client._transport.client = (f'198.51.100.{index + 1}', 40000 + index)
            result.append(await create_ad(client, register_user, email=f'{prefix}-{index}@example.org'))
    finally:
        client._transport.client = original
    return result


async def test_seven_paid_banners_block_eighth_then_expiry_notifies_once(client, register_user, provider):
    campaigns = await campaigns_from_distinct_clients(client, register_user, 'banner')
    admin = await admin_headers(client, register_user)
    for ad, _, headers, _ in campaigns[:7]:
        response = await checkout(client, ad, headers)
        assert response.status_code == 200, response.text
        assert response.json()['amountCents'] == 1000
        await paid(client, provider, response.json()['url'])
        # Duplicate delivery must not produce a second notification or reset payment time.
        duplicate = await webhook(client, provider[response.json()['url'].rsplit('/', 1)[-1]])
        assert duplicate.status_code == 200
    eighth, _, eighth_headers, _ = campaigns[7]
    denied = await checkout(client, eighth, eighth_headers)
    assert denied.status_code == 409 and len(provider) == 7
    assert (await client.get('/api/v1/advertisements/availability')).json()['available'] == 0
    assert (await client.post('/api/v1/advertisements/waitlist', headers=eighth_headers, json={'language': 'ru'})).json()['subscribed']
    assert (await client.get('/api/v1/advertisements/waitlist', headers=eighth_headers)).json()['subscribed']
    async with SessionLocal() as session:
        assert await advertising_alerts.process_advertising_alerts(session) == 0
    for ad, _, _, _ in campaigns[:7]:
        approved = await client.post('/api/v1/admin/advertisements/' + ad['id'] + '/approve', headers=admin, json={})
        assert approved.status_code == 200, approved.text
        value = approved.json()
        assert datetime.fromisoformat(value['endsAt']) - datetime.fromisoformat(value['startsAt']) == timedelta(days=10)
    assert len((await client.get('/api/v1/advertisements/homepage')).json()) == 7
    async with SessionLocal() as session:
        first = await session.get(CommercialAdvertisement, UUID(campaigns[0][0]['id']))
        first.ends_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()
        assert await advertising_alerts.process_advertising_alerts(session) == 1
        assert await advertising_alerts.process_advertising_alerts(session) == 0
        assert await session.scalar(select(func.count(Notification.id)).where(Notification.type == 'advertising_slot_available')) == 1
        assert await session.scalar(select(func.count(Notification.id)).where(Notification.type == 'advertisement_paid')) == 7
    assert len((await client.get('/api/v1/advertisements/homepage')).json()) == 6
    assert (await checkout(client, eighth, eighth_headers)).status_code == 200


async def test_last_slot_concurrent_checkouts_and_double_click(client, register_user, provider):
    campaigns = await campaigns_from_distinct_clients(client, register_user, 'race')
    for ad, _, headers, _ in campaigns[:6]:
        response = await checkout(client, ad, headers)
        await paid(client, provider, response.json()['url'])
    responses = await asyncio.gather(*(checkout(client, ad, headers) for ad, _, headers, _ in campaigns[6:]))
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = campaigns[6] if responses[0].status_code == 200 else campaigns[7]
    duplicated = await asyncio.gather(checkout(client, winner[0], winner[2]), checkout(client, winner[0], winner[2]))
    assert all(response.status_code == 200 for response in duplicated)
    assert duplicated[0].json()['url'] == duplicated[1].json()['url']
    assert len(provider) == 7


async def test_missing_webhook_recovers_from_stripe_status_and_cancel_race_keeps_paid(client, register_user, provider):
    ad, _, headers, _ = await create_ad(client, register_user)
    response = await checkout(client, ad, headers)
    key = response.json()['url'].rsplit('/', 1)[-1]
    provider[key].update(status='complete', payment_status='paid')
    recovered = await client.get('/api/v1/payments/advertisements/' + ad['id'] + '/status', headers=headers)
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()['paymentStatus'] == 'paid'
    assert recovered.json()['fulfillmentStatus'] == 'fulfilled'
    assert (await webhook(client, provider[key])).status_code == 200
    async with SessionLocal() as session:
        assert await session.scalar(select(func.count(Notification.id)).where(Notification.type == 'advertisement_paid')) == 1
    assert (await checkout(client, ad, headers)).status_code == 409


async def test_cancellation_releases_reservation_without_waiting_for_webhook(client, register_user, provider):
    ad, _, headers, _ = await create_ad(client, register_user)
    assert (await checkout(client, ad, headers)).status_code == 200
    assert (await client.get('/api/v1/advertisements/availability')).json()['available'] == 6
    response = await client.post('/api/v1/payments/advertisements/' + ad['id'] + '/checkout/cancel', headers=headers)
    assert response.json() == {'cancelled': True, 'paid': False}
    assert (await client.get('/api/v1/advertisements/availability')).json()['available'] == 7
    assert (await checkout(client, ad, headers)).status_code == 200


async def test_worker_recovers_paid_order_without_any_return_visit(client, register_user, provider):
    ad, _, headers, _ = await create_ad(client, register_user)
    response = await checkout(client, ad, headers)
    remote = provider[response.json()['url'].rsplit('/', 1)[-1]]
    remote.update(status='complete', payment_status='paid')
    async with SessionLocal() as session:
        order = await session.get(PaymentOrder, UUID(remote['client_reference_id']))
        order.created_at = datetime.now(UTC) - timedelta(minutes=1)
        await session.commit()
        await advertising_alerts.process_advertising_alerts(session)
        await session.refresh(order)
        assert order.status == 'paid' and order.fulfillment_status == 'fulfilled'


async def test_paid_changed_creative_requires_review_and_blocks_second_charge(client, register_user, provider):
    ad, _, headers, _ = await create_ad(client, register_user)
    response = await checkout(client, ad, headers)
    async with SessionLocal() as session:
        stored = await session.get(CommercialAdvertisement, UUID(ad['id']))
        stored.title = 'Changed outside checkout'
        await session.commit()
    await paid(client, provider, response.json()['url'])
    status = (await client.get('/api/v1/payments/advertisements/' + ad['id'] + '/status', headers=headers)).json()
    assert status['fulfillmentStatus'] == 'review_required'
    assert (await checkout(client, ad, headers)).status_code == 409
    assert len(provider) == 1
    admin = await admin_headers(client, register_user)
    queue = (await client.get('/api/v1/payments/admin/review-required', headers=admin)).json()
    assert len(queue) == 1 and queue[0]['amountCents'] == 1000
    assert (await client.get('/api/v1/advertisements/mine', headers=headers)).json()[0]['paymentReviewRequired']


async def test_payment_completion_wins_over_concurrent_cancellation(client, register_user, provider):
    ad, _, headers, _ = await create_ad(client, register_user)
    response = await checkout(client, ad, headers)
    remote = provider[response.json()['url'].rsplit('/', 1)[-1]]
    remote.update(status='complete', payment_status='paid')
    result = await client.post('/api/v1/payments/advertisements/' + ad['id'] + '/checkout/cancel', headers=headers)
    assert result.json() == {'cancelled': False, 'paid': True}
    actual = (await client.get('/api/v1/advertisements/' + ad['id'], headers=headers)).json()
    assert actual['status'] == 'pending_review' and actual['paymentStatus'] == 'paid'
    assert (await client.get('/api/v1/advertisements/availability')).json()['available'] == 6


async def test_late_paid_expired_order_cannot_displace_seven_current_purchases(client, register_user, provider):
    campaigns = await campaigns_from_distinct_clients(client, register_user, 'late')
    old, _, headers, _ = campaigns[0]
    old_checkout = await checkout(client, old, headers)
    assert (await client.post('/api/v1/payments/advertisements/' + old['id'] + '/checkout/cancel', headers=headers)).json()['cancelled']
    for ad, _, buyer_headers, _ in campaigns[1:]:
        result = await checkout(client, ad, buyer_headers)
        await paid(client, provider, result.json()['url'])
    await paid(client, provider, old_checkout.json()['url'])
    state = (await client.get('/api/v1/payments/advertisements/' + old['id'] + '/status', headers=headers)).json()
    assert state['orderStatus'] == 'paid' and state['fulfillmentStatus'] == 'review_required'
    assert (await client.get('/api/v1/advertisements/availability')).json()['available'] == 0
    async with SessionLocal() as session:
        assert await session.scalar(select(func.count(CommercialAdvertisement.id)).where(CommercialAdvertisement.payment_status == 'paid')) == 7
