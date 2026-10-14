"""Reproduce BUG-001..007 against PostgreSQL; only Stripe transport is stubbed."""
import asyncio
import hashlib
import hmac
import json
import time
from uuid import UUID, uuid4
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from test_banner_payment_lifecycle import provider, webhook, paid, campaigns_from_distinct_clients
from test_commercial_advertisements import create_ad, admin_headers
from test_homepage_purchase import listing
from app.api.v1 import payments
from app.db.session import SessionLocal
from app.models import User, AuditLog
from app.models.payment_order import PaymentOrder
from app.models.payment_event import PaymentEvent
from app.services import payment_finances

pytestmark = pytest.mark.integration


@pytest.fixture
def finances(monkeypatch, provider):
    objects, refunds, calls = {}, {}, []

    async def retrieve(path):
        if path.startswith('refunds?charge='):
            charge_id = path.split('charge=')[1].split('&')[0]
            matching = [r for r in refunds.values() if r['charge'] == charge_id]
            external = objects['charges/'+charge_id]['amount_refunded'] - sum(r['amount'] for r in matching)
            if external > 0:
                matching.append({'id':'re_external','charge':charge_id,'currency':'eur','status':'succeeded','amount':external})
            return {'data':matching,'has_more':False}
        if path.startswith('refunds?'):
            intent = path.split('payment_intent=')[1].split('&')[0]
            return {'data':[r for r in refunds.values() if r['payment_intent'] == intent], 'has_more':False}
        return dict(objects[path])

    async def refund(order):
        key = (str(order.id), order.refund_attempt)
        calls.append(key)
        charge_id = next(obj['id'] for path,obj in objects.items() if path.startswith('charges/') and obj['payment_intent'] == order.stripe_payment_intent_id)
        receipt = {'id':'re_' + uuid4().hex,'payment_intent':order.stripe_payment_intent_id,'charge':charge_id,
                   'currency':'eur','status':'succeeded','metadata':{'order_id':str(order.id),'attempt':str(order.refund_attempt)}}
        charge = objects['charges/' + charge_id]
        receipt['amount'] = charge['amount'] - charge['amount_refunded']
        charge['amount_refunded'] = charge['amount']
        refunds[receipt['id']] = receipt
        objects['refunds/' + receipt['id']] = receipt
        return receipt

    monkeypatch.setattr(payment_finances,'stripe_object',retrieve)
    monkeypatch.setattr(payment_finances,'retrieve_stripe_session',payments.retrieve_stripe_session)
    monkeypatch.setattr(payment_finances,'create_stripe_refund',refund)
    return objects, refunds, calls


async def financial_event(client, kind, obj, event_id=None):
    body = json.dumps({'id':event_id or 'evt_' + uuid4().hex,'type':kind,'data':{'object':obj}}).encode()
    timestamp = int(time.time())
    signature = hmac.new(b'whsec_review', str(timestamp).encode()+b'.'+body, hashlib.sha256).hexdigest()
    return await client.post('/api/v1/payments/stripe/webhook',content=body,
        headers={'Content-Type':'application/json','Stripe-Signature':f't={timestamp},v1={signature}'})


async def checkout_top(client, register_user, provider, finances, email='audit-top@example.com', *, pay=True):
    target, headers = await listing(client,register_user,email)
    response = await client.post(f'/api/v1/payments/listings/{target}/top/checkout',headers=headers,json={'days':30})
    assert response.status_code == 200, response.text
    key = response.json()['url'].rsplit('/',1)[-1]
    remote = provider[key]
    order_id = remote['client_reference_id']
    intent, charge = 'pi_' + uuid4().hex, 'ch_' + uuid4().hex
    remote['payment_intent'] = intent
    objects, _, _ = finances
    objects['payment_intents/'+intent] = {'id':intent,'metadata':{'order_id':order_id},'status':'succeeded'}
    objects['charges/'+charge] = {'id':charge,'payment_intent':intent,'amount':3000,'amount_refunded':0,'disputed':False,'currency':'eur','livemode':False}
    if pay:
        remote.update(status='complete',payment_status='paid')
        result = await webhook(client,remote)
        assert result.status_code == 200, result.text
    return target, headers, remote, charge, order_id


async def resolve(client, admin, order_id, action='refund'):
    return await client.post(f'/api/v1/payments/admin/orders/{order_id}/resolve',headers=admin,
                            json={'action':action,'reason':'Payment audit resolution test'})


async def test_bug001_async_failure_releases_retry_without_grant(client,register_user,provider,finances):
    target, headers, remote, _, _ = await checkout_top(client,register_user,provider,finances,pay=False)
    remote.update(status='complete',payment_status='unpaid')
    assert (await webhook(client,remote,'checkout.session.async_payment_failed')).status_code == 200
    assert (await webhook(client,remote,'checkout.session.async_payment_failed')).status_code == 200
    state = await client.get(f'/api/v1/payments/listings/{target}/top/status',headers=headers)
    assert state.json()['orderStatus'] == 'failed' and state.json()['endsAt'] is None
    retry = await client.post(f'/api/v1/payments/listings/{target}/top/checkout',headers=headers,json={'days':30})
    assert retry.status_code == 200 and len(provider) == 2


async def test_bug002_paid_listing_and_account_cannot_disappear_before_refund(client,register_user,provider,finances):
    target, headers, _, _, order_id = await checkout_top(client,register_user,provider,finances)
    admin = await admin_headers(client,register_user)
    assert (await client.delete('/api/v1/listings/'+target,headers=headers)).status_code == 409
    assert (await client.delete('/api/v1/listings/'+target,headers=admin)).status_code == 409
    assert (await client.delete('/api/v1/users/me',headers=headers)).status_code == 409
    refunded = await resolve(client,admin,order_id)
    assert refunded.status_code == 200 and refunded.json()['resolved'], refunded.text
    assert (await resolve(client,admin,order_id)).json()['resolved']
    assert len(finances[2]) == 1
    assert (await client.delete('/api/v1/listings/'+target,headers=headers)).status_code == 204
    async with SessionLocal() as db:
        order = await db.get(PaymentOrder,UUID(order_id))
        assert order.status == 'paid' and order.financial_status == 'refunded' and order.fulfillment_status == 'revoked'
        assert order.service_ends_at and order.resolution_actor_id and order.resolved_at
        assert await db.scalar(select(func.count(AuditLog.id)).where(AuditLog.target_id == order.id)) >= 2


async def test_bug003_open_checkout_blocks_account_deletion(client,register_user,provider,finances):
    target, headers, _, _, _ = await checkout_top(client,register_user,provider,finances,pay=False)
    assert (await client.delete('/api/v1/users/me',headers=headers)).status_code == 409
    assert (await client.post(f'/api/v1/payments/listings/{target}/top/checkout/cancel',headers=headers)).json()['cancelled']
    assert (await client.delete('/api/v1/users/me',headers=headers)).status_code == 204


async def test_bug004_dispute_pause_won_restore_refund_and_duplicate_ordering(client,register_user,provider,finances):
    target, _, remote, charge, order_id = await checkout_top(client,register_user,provider,finances)
    objects = finances[0]
    dispute_id = 'du_' + uuid4().hex
    objects['charges/'+charge]['disputed'] = True
    objects['disputes/'+dispute_id] = {'id':dispute_id,'charge':charge,'status':'needs_response'}
    event_id = 'evt_' + uuid4().hex
    result = await financial_event(client,'charge.dispute.created',{'id':dispute_id,'charge':charge},event_id)
    assert result.status_code == 200, result.text
    search = await client.post('/api/v1/listings/search',json={'rentalMode':'long'})
    assert not search.json()['items'][0]['promoted']
    objects['disputes/'+dispute_id]['status'] = 'won'
    assert (await financial_event(client,'charge.dispute.closed',{'id':dispute_id,'charge':charge})).status_code == 200
    # Old created event reads the latest provider state; duplicate delivery is inert.
    assert (await financial_event(client,'charge.dispute.created',{'id':dispute_id,'charge':charge},event_id)).status_code == 200
    search = await client.post('/api/v1/listings/search',json={'rentalMode':'long'})
    assert search.json()['items'][0]['promoted']
    objects['charges/'+charge]['amount_refunded'] = 3000
    assert (await financial_event(client,'charge.refunded',{'id':charge})).status_code == 200
    assert (await webhook(client,remote)).status_code == 200
    search = await client.post('/api/v1/listings/search',json={'rentalMode':'long'})
    assert not search.json()['items'][0]['promoted']
    async with SessionLocal() as db:
        order = await db.get(PaymentOrder,UUID(order_id))
        assert order.refunded_amount_cents == 3000 and order.financial_status == 'refunded'
        assert await db.scalar(select(func.count(PaymentEvent.id))) == 3


async def test_bug004_financial_event_before_checkout_never_grants_refunded_top(client,register_user,provider,finances):
    target, _, remote, charge, _ = await checkout_top(client,register_user,provider,finances,pay=False)
    finances[0]['charges/'+charge]['amount_refunded'] = 3000
    assert (await financial_event(client,'charge.refunded',{'id':charge})).status_code == 200
    remote.update(status='complete',payment_status='paid')
    assert (await webhook(client,remote)).status_code == 200
    result = await client.post('/api/v1/listings/search',json={'rentalMode':'long'})
    assert not result.json()['items'][0]['promoted']


async def test_bug005_paid_rejected_banner_retains_seventh_place(client,register_user,provider):
    # Create eight drafts before any payment reserves capacity.
    drafts = await campaigns_from_distinct_clients(client,register_user,'fix-banner')
    for ad, _, headers, _ in drafts[:7]:
        result = await client.post(f"/api/v1/payments/advertisements/{ad['id']}/checkout",headers=headers)
        assert result.status_code == 200, result.text
        await paid(client,provider,result.json()['url'])
    admin = await admin_headers(client,register_user)
    first, payload, headers, _ = drafts[0]
    assert (await client.post(f"/api/v1/admin/advertisements/{first['id']}/reject",headers=admin,json={'note':'Fix wording'})).status_code == 200
    eighth, _, other, _ = drafts[7]
    denied = await client.post(f"/api/v1/payments/advertisements/{eighth['id']}/checkout",headers=other)
    assert denied.status_code == 409
    payload['title'] = 'Corrected local service'
    corrected = await client.patch('/api/v1/advertisements/'+first['id'],headers=headers,json=payload)
    assert corrected.status_code == 200 and corrected.json()['status'] == 'pending_review', corrected.text


async def test_bug006_slow_stripe_does_not_hold_global_sales_lock(client,register_user,provider):
    first, headers = await listing(client,register_user,'slow-first@example.com')
    other, other_headers = await listing(client,register_user,'slow-second@example.com')
    original = payments.create_stripe_session
    started, release = asyncio.Event(), asyncio.Event()

    async def slow(order,*args):
        if str(order.target_id) == first:
            started.set()
            await release.wait()
        return await original(order,*args)

    from unittest.mock import patch
    with patch.object(payments,'create_stripe_session',slow):
        waiting = asyncio.create_task(client.post(f'/api/v1/payments/listings/{first}/top/checkout',headers=headers,json={'days':30}))
        await asyncio.wait_for(started.wait(),5)
        try:
            second = await asyncio.wait_for(client.post(f'/api/v1/payments/listings/{other}/top/checkout',headers=other_headers,json={'days':30}),2)
            assert second.status_code == 200, second.text
            # The first durable order must already exist despite delayed provider IO.
            async with SessionLocal() as db:
                order = await db.scalar(select(PaymentOrder).where(PaymentOrder.target_id == UUID(first)))
                assert order.status == 'creating'
        finally:
            release.set()
        assert (await waiting).status_code == 200


async def test_bug006_commit_failure_recovers_same_reserved_order(client,register_user,provider,monkeypatch):
    target, headers = await listing(client,register_user,'commit-failure@example.com')
    original = AsyncSession.commit
    failed = False

    async def fail_finalize(db):
        nonlocal failed
        if not failed and any(isinstance(row,PaymentOrder) and row.status == 'pending' and row.stripe_session_id for row in db.dirty):
            failed = True
            raise RuntimeError('Simulated commit failure')
        await original(db)

    monkeypatch.setattr(AsyncSession,'commit',fail_finalize)
    with pytest.raises(RuntimeError,match='Simulated commit failure'):
        await client.post(f'/api/v1/payments/listings/{target}/top/checkout',headers=headers,json={'days':30})
    result = await client.post(f'/api/v1/payments/listings/{target}/top/checkout',headers=headers,json={'days':30})
    assert result.status_code == 200 and len(provider) == 1, result.text
    async with SessionLocal() as db:
        assert await db.scalar(select(func.count(PaymentOrder.id)).where(PaymentOrder.target_id == UUID(target))) == 1


async def test_bug007_review_can_restore_once_with_operator_audit(client,register_user,provider,finances):
    target, headers, remote, _, order_id = await checkout_top(client,register_user,provider,finances,pay=False)
    async with SessionLocal() as db:
        from app.models import Listing
        row = await db.get(Listing,UUID(target)); row.status = 'hidden'; await db.commit()
    remote.update(status='complete',payment_status='paid')
    assert (await webhook(client,remote)).status_code == 200
    admin = await admin_headers(client,register_user)
    assert (await resolve(client,admin,order_id,'restore')).json()['resolved'] is False
    async with SessionLocal() as db:
        from app.models import Listing
        row = await db.get(Listing,UUID(target)); row.status = 'published'; await db.commit()
    restored = await resolve(client,admin,order_id,'restore')
    assert restored.status_code == 200 and restored.json()['resolved'], restored.text
    assert (await resolve(client,admin,order_id,'restore')).json()['resolved']
    async with SessionLocal() as db:
        order = await db.get(PaymentOrder,UUID(order_id))
        assert order.resolved_at and order.resolution_actor_id and order.service_ends_at
        assert await db.scalar(select(func.count(AuditLog.id)).where(AuditLog.target_id == order.id,AuditLog.action == 'payment.restored')) == 1


async def test_partial_refund_is_reviewed_and_remaining_balance_refunded_once(client,register_user,provider,finances):
    target, _, _, charge, order_id = await checkout_top(client,register_user,provider,finances)
    finances[0]['charges/'+charge]['amount_refunded'] = 1000
    assert (await financial_event(client,'charge.refunded',{'id':charge})).status_code == 200
    admin = await admin_headers(client,register_user)
    queue = (await client.get('/api/v1/payments/admin/review-required',headers=admin)).json()
    assert queue[0]['id'] == order_id and queue[0]['financialStatus'] == 'partial_refund'
    assert (await resolve(client,admin,order_id,'restore')).status_code == 409
    result = await resolve(client,admin,order_id)
    assert result.status_code == 200 and result.json()['resolved'], result.text
    assert next(iter(finances[1].values()))['amount'] == 2000
    assert (await resolve(client,admin,order_id)).json()['resolved'] and len(finances[2]) == 1


async def test_refund_commit_failure_reuses_provider_receipt(client,register_user,provider,finances,monkeypatch):
    _, _, _, _, order_id = await checkout_top(client,register_user,provider,finances)
    admin = await admin_headers(client,register_user)
    original = AsyncSession.commit
    failed = False

    async def fail_receipt(db):
        nonlocal failed
        if not failed and any(isinstance(row,PaymentOrder) and row.financial_status == 'refunded' for row in db.identity_map.values()):
            failed = True
            raise RuntimeError('Refund receipt commit failure')
        await original(db)

    monkeypatch.setattr(AsyncSession,'commit',fail_receipt)
    with pytest.raises(RuntimeError,match='Refund receipt commit failure'):
        await resolve(client,admin,order_id)
    retried = await resolve(client,admin,order_id)
    assert retried.status_code == 200 and retried.json()['resolved'], retried.text
    assert len(finances[2]) == 1


async def test_pending_failed_refund_does_not_revoke_or_replay_after_restore(client,register_user,provider,finances):
    target, _, remote, charge, order_id = await checkout_top(client,register_user,provider,finances)
    receipt = {'id':'re_' + uuid4().hex,'charge':charge,'payment_intent':remote['payment_intent'],
               'amount':3000,'currency':'eur','status':'pending','metadata':{}}
    finances[1][receipt['id']] = receipt
    finances[0]['refunds/'+receipt['id']] = receipt
    finances[0]['charges/'+charge]['amount_refunded'] = 3000
    assert (await financial_event(client,'refund.created',{'id':receipt['id'],'charge':charge})).status_code == 200
    async with SessionLocal() as db:
        order = await db.get(PaymentOrder,UUID(order_id))
        original_end = order.service_ends_at
        assert order.financial_status == 'refund_pending' and order.refunded_amount_cents == 0
    receipt['status'] = 'failed'
    finances[0]['charges/'+charge]['amount_refunded'] = 0
    assert (await financial_event(client,'refund.failed',{'id':receipt['id'],'charge':charge})).status_code == 200
    admin = await admin_headers(client,register_user)
    restored = await resolve(client,admin,order_id,'restore')
    assert restored.status_code == 200 and restored.json()['resolved'], restored.text
    assert (await webhook(client,remote)).status_code == 200
    async with SessionLocal() as db:
        order = await db.get(PaymentOrder,UUID(order_id))
        assert order.financial_status == 'normal' and order.service_ends_at == original_end
    result = await client.post('/api/v1/listings/search',json={'rentalMode':'long'})
    assert result.json()['items'][0]['promoted']


async def test_unknown_checkout_after_idempotency_window_requires_verified_reconciliation(client,register_user,provider,finances):
    target, headers, remote, _, order_id = await checkout_top(client,register_user,provider,finances,pay=False)
    verified_id = 'cs_test_' + uuid4().hex
    remote['id'] = verified_id
    remote['status'] = 'expired'
    provider[verified_id] = remote
    async with SessionLocal() as db:
        order = await db.get(PaymentOrder,UUID(order_id))
        order.status, order.stripe_session_id, order.checkout_url = 'creating', None, None
        order.created_at = datetime.now(UTC)-timedelta(hours=24)
        await db.commit()
    blocked = await client.post(f'/api/v1/payments/listings/{target}/top/checkout',headers=headers,json={'days':30})
    assert blocked.status_code == 409
    admin = await admin_headers(client,register_user)
    result = await client.post(f'/api/v1/payments/admin/orders/{order_id}/resolve',headers=admin,
        json={'action':'reconcile','reason':'Verified expired Stripe session','stripeSessionId':verified_id})
    assert result.status_code == 200 and result.json()['status'] == 'expired', result.text


async def test_refund_of_ungranted_order_preserves_independent_admin_top(client,register_user,provider,finances):
    target, _, remote, _, order_id = await checkout_top(client,register_user,provider,finances,pay=False)
    admin = await admin_headers(client,register_user)
    actor = (await client.get('/api/v1/auth/me',headers=admin)).json()['id']
    async with SessionLocal() as db:
        from app.models.moderation import ListingPromotion
        db.add(ListingPromotion(listing_id=UUID(target),boosted_by=UUID(actor),
            starts_at=datetime.now(UTC)-timedelta(days=1),ends_at=None))
        await db.commit()
    remote.update(status='complete',payment_status='paid')
    assert (await webhook(client,remote)).status_code == 200
    refunded = await resolve(client,admin,order_id)
    assert refunded.status_code == 200 and refunded.json()['resolved'], refunded.text
    result = await client.post('/api/v1/listings/search',json={'rentalMode':'long'})
    assert result.json()['items'][0]['promoted']


async def test_refund_of_renewal_preserves_original_top_period_and_rank(client,register_user,provider,finances):
    target, headers, _, _, first_id = await checkout_top(client,register_user,provider,finances)
    async with SessionLocal() as db:
        first = await db.get(PaymentOrder,UUID(first_id))
        original_end, original_rank = first.service_ends_at, first.paid_at
    response = await client.post(f'/api/v1/payments/listings/{target}/top/checkout',headers=headers,json={'days':30})
    remote = provider[response.json()['url'].rsplit('/',1)[-1]]
    intent, charge = 'pi_' + uuid4().hex,'ch_' + uuid4().hex
    remote.update(status='complete',payment_status='paid',payment_intent=intent)
    finances[0]['payment_intents/'+intent] = {'id':intent,'metadata':{'order_id':remote['client_reference_id']}}
    finances[0]['charges/'+charge] = {'id':charge,'payment_intent':intent,'amount':3000,'amount_refunded':0,'disputed':False,'currency':'eur','livemode':False}
    assert (await webhook(client,remote)).status_code == 200
    admin = await admin_headers(client,register_user)
    refunded = await resolve(client,admin,remote['client_reference_id'])
    assert refunded.status_code == 200 and refunded.json()['resolved'], refunded.text
    async with SessionLocal() as db:
        from app.models.moderation import ListingPromotion
        promotion = await db.get(ListingPromotion,UUID(target))
        assert promotion.ends_at == original_end and promotion.boosted_at == original_rank
        assert promotion.total_price_cents == 3000
    result = await client.post('/api/v1/listings/search',json={'rentalMode':'long'})
    assert result.json()['items'][0]['promoted']
