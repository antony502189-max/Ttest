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
from app.models import MediaAsset, Notification, User
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
        assert response.json()['amountCents'] == 3000
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
        from app.services.homepage_purchase import one_month_after
        assert datetime.fromisoformat(value['endsAt']) == one_month_after(datetime.fromisoformat(value['startsAt']))
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
    assert len(queue) == 1 and queue[0]['amountCents'] == 3000
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


async def premium_campaign(client, register_user, email):
    ad, payload, headers, user = await create_ad(client, register_user, email=email)
    payload['packageId'] = 'homepage_premium_1m'
    changed = await client.patch('/api/v1/advertisements/' + ad['id'], headers=headers, json=payload)
    assert changed.status_code == 200, changed.text
    return changed.json(), payload, headers, user


async def test_premium_concurrent_purchases_and_duplicate_requests(client, register_user, provider):
    campaigns = [await premium_campaign(client, register_user, f'premium-race-{i}@example.org') for i in range(2)]
    responses = await asyncio.gather(*(checkout(client, ad, headers) for ad, _, headers, _ in campaigns))
    assert sorted(r.status_code for r in responses) == [200, 409]
    winner = campaigns[0 if responses[0].status_code == 200 else 1]
    duplicates = await asyncio.gather(*(checkout(client, winner[0], winner[2]) for _ in range(2)))
    assert all(r.status_code == 200 and r.json()['amountCents'] == 6000 for r in duplicates)
    assert duplicates[0].json()['url'] == duplicates[1].json()['url']
    assert len(provider) == 1
    remote = await paid(client, provider, duplicates[0].json()['url'])
    assert (await webhook(client, remote)).status_code == 200
    assert (await webhook(client, {**remote, 'payment_status': 'unpaid'}, 'checkout.session.expired')).status_code == 200
    availability = (await client.get('/api/v1/advertisements/availability')).json()
    assert availability['premiumAvailable'] == 0 and availability['available'] == 7


async def test_standard_and_premium_inventory_are_independent(client, register_user, provider):
    campaigns = await campaigns_from_distinct_clients(client, register_user, 'independent')
    premium = await premium_campaign(client, register_user, 'independent-premium@example.org')
    responses = await asyncio.gather(*(checkout(client, ad, headers) for ad, _, headers, _ in campaigns[:7]))
    assert all(r.status_code == 200 and r.json()['amountCents'] == 3000 for r in responses)
    result = await checkout(client, premium[0], premium[2])
    assert result.status_code == 200 and result.json()['amountCents'] == 6000
    assert (await checkout(client, campaigns[7][0], campaigns[7][2])).status_code == 409
    availability = (await client.get('/api/v1/advertisements/availability')).json()
    assert availability['premiumAvailable'] == availability['available'] == 0


async def test_paid_premium_recovery_rechecks_capacity_on_every_retry(client, register_user, provider, monkeypatch):
    old = await premium_campaign(client, register_user, 'old-premium@example.org')
    new = await premium_campaign(client, register_user, 'new-premium@example.org')
    first = await checkout(client, old[0], old[2])
    assert (await client.post('/api/v1/payments/advertisements/' + old[0]['id'] + '/checkout/cancel', headers=old[2])).json()['cancelled']
    replacement = await checkout(client, new[0], new[2])
    await paid(client, provider, replacement.json()['url'])
    remote = await paid(client, provider, first.json()['url'])
    from app.services import payment_finances
    monkeypatch.setattr(payment_finances, 'retrieve_stripe_session', payments.retrieve_stripe_session)
    admin = await admin_headers(client, register_user)
    for _ in range(2):
        restored = await client.post('/api/v1/payments/admin/orders/' + remote['client_reference_id'] + '/resolve',
                                     headers=admin, json={'action': 'restore', 'reason': 'Retry delayed premium payment'})
        assert restored.status_code == 200 and restored.json()['resolved'] is False, restored.text
    async with SessionLocal() as db:
        order = await db.get(PaymentOrder, UUID(remote['client_reference_id']))
        old_ad = await db.get(CommercialAdvertisement, UUID(old[0]['id']))
        assert order.status == 'paid' and order.fulfillment_status == 'review_required'
        assert old_ad.payment_status == 'unpaid'
    # Seed the competing campaign's post-refund state; financial webhook tests
    # separately exercise the provider-confirmed refund transition.
    async with SessionLocal() as db:
        other = await db.get(CommercialAdvertisement, UUID(new[0]['id']))
        other.status, other.payment_status = 'cancelled', 'refunded'
        await db.commit()
    restored = await client.post('/api/v1/payments/admin/orders/' + remote['client_reference_id'] + '/resolve',
                                 headers=admin, json={'action': 'restore', 'reason': 'Retry after inventory release'})
    assert restored.status_code == 200 and restored.json()['resolved'] is True, restored.text


async def test_expired_checkout_replacement_race_creates_only_one_new_order(client, register_user, provider, monkeypatch):
    ad, _, headers, _ = await create_ad(client, register_user)
    initial = await checkout(client, ad, headers)
    key = initial.json()['url'].rsplit('/', 1)[-1]
    provider[key]['status'] = 'expired'
    original = payments.retrieve_stripe_session
    both_read = asyncio.Event()
    readers = 0

    async def synchronize(key_to_read):
        nonlocal readers
        if key_to_read == key:
            readers += 1
            if readers == 2:
                both_read.set()
            await asyncio.wait_for(both_read.wait(), 5)
        return await original(key_to_read)

    monkeypatch.setattr(payments, 'retrieve_stripe_session', synchronize)
    responses = await asyncio.gather(checkout(client, ad, headers), checkout(client, ad, headers))
    assert all(r.status_code == 200 for r in responses)
    assert responses[0].json()['url'] == responses[1].json()['url']
    async with SessionLocal() as db:
        assert await db.scalar(select(func.count(PaymentOrder.id)).where(
            PaymentOrder.target_id == UUID(ad['id']), PaymentOrder.status.in_(['creating', 'pending']),
        )) == 1
    assert len(provider) == 2


async def test_checkout_revalidates_campaign_after_provider_io(client, register_user, provider, monkeypatch):
    ad, payload, headers, _ = await create_ad(client, register_user)
    initial = await checkout(client, ad, headers)
    key = initial.json()['url'].rsplit('/', 1)[-1]
    provider[key]['status'] = 'expired'
    original = payments.retrieve_stripe_session

    async def expire_then_change(key_to_read):
        # Another request can process expiry and edit while this GET has no lock.
        assert (await webhook(client, provider[key], 'checkout.session.expired')).status_code == 200
        changed = await client.patch('/api/v1/advertisements/' + ad['id'], headers=headers,
                                     json={**payload, 'packageId': 'homepage_premium_1m'})
        assert changed.status_code == 200, changed.text
        return await original(key_to_read)

    monkeypatch.setattr(payments, 'retrieve_stripe_session', expire_then_change)
    response = await checkout(client, ad, headers)
    assert response.status_code == 200, response.text
    assert response.json()['amountCents'] == 6000
    newest = provider[response.json()['url'].rsplit('/', 1)[-1]]
    assert newest['amount_total'] == 6000


async def test_checkout_rejects_unknown_and_mismatched_package_in_database(client, register_user, provider):
    ad, _, headers, _ = await create_ad(client, register_user)
    for package, placement in [('unsupported', 'homepage_bottom'), ('homepage_1d', 'homepage_premium')]:
        async with SessionLocal() as db:
            stored = await db.get(CommercialAdvertisement, UUID(ad['id']))
            stored.package_id, stored.placement = package, placement
            await db.commit()
        assert (await checkout(client, ad, headers)).status_code == 409
    assert not provider


@pytest.mark.parametrize('defect', ['placement', 'blocked_owner', 'deleted_image'])
async def test_payment_cannot_fulfill_invalid_campaign(client, register_user, provider, defect):
    ad, _, headers, user = await create_ad(client, register_user)
    result = await checkout(client, ad, headers)
    async with SessionLocal() as db:
        stored = await db.get(CommercialAdvertisement, UUID(ad['id']))
        if defect == 'placement':
            stored.placement = 'homepage_premium'
        elif defect == 'blocked_owner':
            owner = await db.get(User, UUID(user['id']))
            owner.blocked = True
        else:
            asset = await db.get(MediaAsset, stored.image_asset_id)
            asset.deleted_at = datetime.now(UTC)
        await db.commit()
    remote = await paid(client, provider, result.json()['url'])
    async with SessionLocal() as db:
        order = await db.get(PaymentOrder, UUID(remote['client_reference_id']))
        assert order.status == 'paid' and order.fulfillment_status == 'review_required'
        stored = await db.get(CommercialAdvertisement, UUID(ad['id']))
        assert stored.payment_status == 'unpaid'


async def test_paid_edit_cannot_move_original_month_by_moderator_override(client, register_user, provider):
    ad, payload, headers, _ = await premium_campaign(client, register_user, 'premium-edit@example.org')
    result = await checkout(client, ad, headers)
    await paid(client, provider, result.json()['url'])
    admin = await admin_headers(client, register_user)
    approved = await client.post('/api/v1/admin/advertisements/' + ad['id'] + '/approve', headers=admin, json={})
    assert approved.status_code == 200, approved.text
    start = datetime.fromisoformat(approved.json()['startsAt'])
    end = datetime.fromisoformat(approved.json()['endsAt'])
    from app.services.homepage_purchase import one_month_after
    assert end == one_month_after(start)
    assert (await client.patch('/api/v1/advertisements/' + ad['id'], headers=headers,
                               json={**payload, 'packageId': 'homepage_1d'})).status_code == 409
    edited = await client.patch('/api/v1/advertisements/' + ad['id'], headers=headers,
                                json={**payload, 'title': 'Changed paid premium creative'})
    assert edited.status_code == 200
    shifted = await client.post('/api/v1/admin/advertisements/' + ad['id'] + '/approve', headers=admin,
                                 json={'startsAt': (start + timedelta(days=1)).isoformat(),
                                       'endsAt': one_month_after(start + timedelta(days=1)).isoformat()})
    assert shifted.status_code == 422
    again = await client.post('/api/v1/admin/advertisements/' + ad['id'] + '/approve', headers=admin, json={})
    assert again.status_code == 200 and again.json()['endsAt'] == approved.json()['endsAt']


async def test_checkout_ownership_price_tampering_and_pending_package_edit(client, register_user, provider):
    ad, payload, headers, _ = await premium_campaign(client, register_user, 'tamper-premium@example.org')
    _, _, outsider, _ = await create_ad(client, register_user, email='outsider@example.org')
    for path in ['checkout', 'quote', 'status', 'checkout/cancel']:
        request = client.post if path in {'checkout', 'checkout/cancel'} else client.get
        response = await request('/api/v1/payments/advertisements/' + ad['id'] + '/' + path, headers=outsider)
        assert response.status_code == 404, response.text
    invalid = await client.patch('/api/v1/advertisements/' + ad['id'], headers=headers,
                                  json={**payload, 'packageId': 'homepage_premium_free'})
    assert invalid.status_code == 422
    response = await client.post('/api/v1/payments/advertisements/' + ad['id'] + '/checkout', headers=headers,
                                  json={'amountCents': 1, 'currency': 'USD', 'packageId': 'homepage_1d'})
    assert response.status_code == 200 and response.json()['amountCents'] == 6000
    assert next(iter(provider.values()))['amount_total'] == 6000
    edit = await client.patch('/api/v1/advertisements/' + ad['id'], headers=headers,
                              json={**payload, 'packageId': 'homepage_1d'})
    assert edit.status_code == 409
    # Local age alone never releases a potentially paid premium reservation.
    async with SessionLocal() as db:
        order = await db.scalar(select(PaymentOrder).where(PaymentOrder.target_id == UUID(ad['id'])))
        order.created_at = datetime.now(UTC) - timedelta(days=2)
        await db.commit()
        await advertising_alerts.process_advertising_alerts(db)
    availability = (await client.get('/api/v1/advertisements/availability')).json()
    assert availability['premiumAvailable'] == 0


async def test_expired_premium_renewal_requires_new_payment(client, register_user, provider):
    ad, payload, headers, _ = await premium_campaign(client, register_user, 'renew-premium@example.org')
    first = await checkout(client, ad, headers)
    remote = await paid(client, provider, first.json()['url'])
    admin = await admin_headers(client, register_user)
    approved = await client.post('/api/v1/admin/advertisements/' + ad['id'] + '/approve', headers=admin, json={})
    assert approved.status_code == 200
    async with SessionLocal() as db:
        stored = await db.get(CommercialAdvertisement, UUID(ad['id']))
        stored.ends_at = datetime.now(UTC) - timedelta(seconds=1)
        await db.commit()
    assert (await checkout(client, ad, headers)).status_code == 409
    edited = await client.patch('/api/v1/advertisements/' + ad['id'], headers=headers, json=payload)
    assert edited.status_code == 200 and edited.json()['paymentStatus'] == 'unpaid'
    assert edited.json()['startsAt'] is None and edited.json()['endsAt'] is None
    assert (await client.post('/api/v1/admin/advertisements/' + ad['id'] + '/approve', headers=admin, json={})).status_code == 409
    second = await checkout(client, ad, headers)
    assert second.status_code == 200 and second.json()['amountCents'] == 6000
    assert second.json()['url'] != first.json()['url']
    assert (await webhook(client, remote)).status_code == 200  # old receipt cannot renew
    unchanged = (await client.get('/api/v1/advertisements/' + ad['id'], headers=headers)).json()
    assert unchanged['paymentStatus'] == 'unpaid'
    await paid(client, provider, second.json()['url'])
    assert (await client.post('/api/v1/admin/advertisements/' + ad['id'] + '/approve', headers=admin, json={})).status_code == 200


async def test_legacy_paid_edit_preserves_package_and_original_expiry(client, register_user, provider):
    ad, payload, headers, _ = await create_ad(client, register_user)
    start = datetime.now(UTC) - timedelta(days=2)
    end = start + timedelta(days=30)
    async with SessionLocal() as db:
        stored = await db.get(CommercialAdvertisement, UUID(ad['id']))
        stored.status, stored.payment_status = 'active', 'paid'
        stored.package_id = 'test_homepage_30d'
        stored.starts_at, stored.ends_at = start, end
        await db.commit()
    edited = await client.patch('/api/v1/advertisements/' + ad['id'], headers=headers,
                                json={**payload, 'title': 'Updated legacy campaign'})
    assert edited.status_code == 200, edited.text
    assert edited.json()['packageId'] == 'test_homepage_30d'
    assert datetime.fromisoformat(edited.json()['endsAt']) == end
    admin = await admin_headers(client, register_user)
    approved = await client.post('/api/v1/admin/advertisements/' + ad['id'] + '/approve', headers=admin, json={})
    assert approved.status_code == 200 and datetime.fromisoformat(approved.json()['endsAt']) == end
    assert not provider


async def test_legacy_order_keeps_original_amount_and_day_entitlement(client, register_user, provider):
    ad, _, _, user = await create_ad(client, register_user)
    async with SessionLocal() as db:
        order = PaymentOrder(owner_user_id=UUID(user['id']), kind='advertisement', target_id=UUID(ad['id']),
                             days=1, amount_cents=1000, status='pending', stripe_session_id='cs_legacy_standard')
        db.add(order)
        await db.flush()
        order_id = order.id
        await db.commit()
    remote = {'id': 'cs_legacy_standard', 'client_reference_id': str(order_id), 'amount_total': 1000,
              'currency': 'eur', 'livemode': False, 'status': 'complete', 'payment_status': 'paid'}
    assert (await webhook(client, remote)).status_code == 200
    admin = await admin_headers(client, register_user)
    approved = await client.post('/api/v1/admin/advertisements/' + ad['id'] + '/approve', headers=admin, json={})
    assert approved.status_code == 200, approved.text
    assert (datetime.fromisoformat(approved.json()['endsAt']) - datetime.fromisoformat(approved.json()['startsAt'])) == timedelta(days=1)
    async with SessionLocal() as db:
        order = await db.get(PaymentOrder, order_id)
        assert order.amount_cents == 1000 and order.duration_months is None


async def test_concurrent_premium_approval_and_admin_gift_cannot_overbook(client, register_user, provider):
    ad, _, headers, _ = await premium_campaign(client, register_user, 'approve-premium@example.org')
    result = await checkout(client, ad, headers)
    await paid(client, provider, result.json()['url'])
    _, gift, _, _ = await create_ad(client, register_user, email='gift-image@example.org')
    admin = await admin_headers(client, register_user)
    # Administrator gifts must use an image belonging to that administrator.
    from test_commercial_advertisements import image_file
    upload = await client.post('/api/v1/advertisements/uploads', headers=admin,
                               files={'file': ('gift.png', image_file('premium-gift'), 'image/png')})
    assert upload.status_code == 201
    gift = {**gift, 'imageAssetId': upload.json()['id'], 'packageId': 'homepage_premium_1m'}
    approve, complimentary = await asyncio.gather(
        client.post('/api/v1/admin/advertisements/' + ad['id'] + '/approve', headers=admin, json={}),
        client.post('/api/v1/admin/advertisements', headers=admin, json=gift),
    )
    assert approve.status_code == 200 and complimentary.status_code == 409
    assert len((await client.get('/api/v1/advertisements/premium')).json()) == 1
