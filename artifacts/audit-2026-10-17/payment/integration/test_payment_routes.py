import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
import test_banner_payment_lifecycle as lifecycle
import test_payment_audit as audit_helpers
from test_commercial_advertisements import admin_headers
from test_homepage_purchase import listing

from app.db.session import SessionLocal
from app.models import Listing, Notification, User
from app.models.moderation import ListingPromotion, UserRestriction
from app.models.payment_order import PaymentOrder

provider = lifecycle.provider
finances = audit_helpers.finances


async def target(client, register_user, email, postcode='28013'):
    listing_id, headers = await listing(client, register_user, email)
    changed = await client.patch('/api/v1/listings/' + listing_id, headers=headers, json={'postcode': postcode})
    assert changed.status_code == 200, changed.text
    return listing_id, headers


async def checkout(client, listing_id, headers):
    return await client.post(f'/api/v1/payments/listings/{listing_id}/top/checkout', headers=headers, json={'days': 30})


async def purchase(client, provider, listing_id, headers, *, intent=None):
    result = await checkout(client, listing_id, headers)
    assert result.status_code == 200, result.text
    remote = provider[result.json()['url'].rsplit('/', 1)[-1]]
    remote.update(status='complete', payment_status='paid')
    if intent:
        remote['payment_intent'] = intent
    response = await lifecycle.webhook(client, remote)
    assert response.status_code == 200, response.text
    return remote


async def availability(client, listing_id, headers):
    result = await client.get(f'/api/v1/payments/listings/{listing_id}/top/availability', headers=headers)
    assert result.status_code == 200, result.text
    return result.json()


async def test_A_C_E_I_J_final_slot_and_duplicate_requests_events(client, register_user, provider):
    targets = [await target(client, register_user, f'province-race-{i}@example.com') for i in range(4)]
    assert (await availability(client, *targets[3]))['availableSlots'] == 3
    for index, (listing_id, headers) in enumerate(targets[:2]):
        await purchase(client, provider, listing_id, headers)
        assert (await availability(client, *targets[3]))['availableSlots'] == 2 - index
    responses = await asyncio.gather(*(checkout(client, listing_id, headers) for listing_id, headers in targets[2:]))
    assert sorted(r.status_code for r in responses) == [200, 409]
    winner = next(i + 2 for i, response in enumerate(responses) if response.status_code == 200)
    listing_id, headers = targets[winner]
    repeated = await asyncio.gather(checkout(client, listing_id, headers), checkout(client, listing_id, headers))
    assert all(r.status_code == 200 for r in repeated)
    assert repeated[0].json()['url'] == repeated[1].json()['url']
    assert len(provider) == 3
    remote = provider[repeated[0].json()['url'].rsplit('/', 1)[-1]]
    remote.update(status='complete', payment_status='paid')
    delivered = await asyncio.gather(*(lifecycle.webhook(client, remote) for _ in range(3)))
    assert all(r.status_code == 200 for r in delivered)
    async with SessionLocal() as db:
        assert await db.scalar(select(func.count()).select_from(ListingPromotion)) == 3
        assert await db.scalar(select(func.count()).select_from(PaymentOrder)) == 3
        assert await db.scalar(select(func.count()).select_from(Notification).where(Notification.type == 'listing_top_paid')) == 3
    loser = targets[3 if winner == 2 else 2]
    assert (await checkout(client, *loser)).status_code == 409
    assert (await availability(client, *loser))['availableSlots'] == 0
    elsewhere = await target(client, register_user, 'province-other@example.com', '08001')
    other = await availability(client, *elsewhere)
    assert other['available'] and other['availableSlots'] == 3
    await purchase(client, provider, *elsewhere)
    assert (await availability(client, *loser))['availableSlots'] == 0


async def test_B_late_success_after_expiry_goes_to_review_when_capacity_refilled(client, register_user, provider):
    old_id, old_headers = await target(client, register_user, 'late-old@example.com')
    started = await checkout(client, old_id, old_headers)
    remote = provider[started.json()['url'].rsplit('/', 1)[-1]]
    remote['status'] = 'expired'
    assert (await lifecycle.webhook(client, remote, 'checkout.session.expired')).status_code == 200
    for i in range(3):
        new_id, new_headers = await target(client, register_user, f'late-new-{i}@example.com')
        await purchase(client, provider, new_id, new_headers)
    remote.update(status='complete', payment_status='paid')
    assert (await lifecycle.webhook(client, remote)).status_code == 200
    async with SessionLocal() as db:
        order = await db.get(PaymentOrder, UUID(remote['client_reference_id']))
        assert order.status == 'paid' and order.fulfillment_status == 'review_required'
        assert await db.get(ListingPromotion, UUID(old_id)) is None
        assert await db.scalar(select(func.count()).select_from(ListingPromotion)) == 3


async def test_D_H_browser_never_returns_and_callback_retry_recovers(client, register_user, provider):
    listing_id, headers = await target(client, register_user, 'recovery@example.com')
    started = await checkout(client, listing_id, headers)
    remote = provider[started.json()['url'].rsplit('/', 1)[-1]]
    remote.update(status='complete', payment_status='paid')
    # No redirect / webhook: the background worker reconciles Stripe state.
    async with SessionLocal() as db:
        order = await db.get(PaymentOrder, UUID(remote['client_reference_id']))
        order.created_at = datetime.now(UTC) - timedelta(minutes=1)
        await db.commit()
    from app.services.advertising_alerts import process_advertising_alerts
    async with SessionLocal() as db:
        await process_advertising_alerts(db)
    async with SessionLocal() as db:
        order = await db.get(PaymentOrder, UUID(remote['client_reference_id']))
        assert order.fulfillment_status == 'fulfilled'
        before = (await db.get(ListingPromotion, UUID(listing_id))).ends_at
    assert (await lifecycle.webhook(client, remote)).status_code == 200
    async with SessionLocal() as db:
        assert (await db.get(ListingPromotion, UUID(listing_id))).ends_at == before


async def test_H_callback_commit_failure_rolls_back_and_retry_grants_once(client, register_user, provider, monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncSession
    listing_id, headers = await target(client, register_user, 'callback-crash@example.com')
    started = await checkout(client, listing_id, headers)
    remote = provider[started.json()['url'].rsplit('/', 1)[-1]]
    remote.update(status='complete', payment_status='paid')
    original_commit = AsyncSession.commit
    failed = False

    async def fail_fulfillment_commit(db):
        nonlocal failed
        if not failed and any(isinstance(row, PaymentOrder) and row.status == 'paid' for row in db.identity_map.values()):
            failed = True
            raise RuntimeError('Isolated audit: crash before fulfillment commit')
        await original_commit(db)

    monkeypatch.setattr(AsyncSession, 'commit', fail_fulfillment_commit)
    with pytest.raises(RuntimeError, match='crash before fulfillment commit'):
        await lifecycle.webhook(client, remote)
    async with SessionLocal() as db:
        order = await db.get(PaymentOrder, UUID(remote['client_reference_id']))
        assert order.status == 'pending'
        assert await db.get(ListingPromotion, UUID(listing_id)) is None
    assert (await lifecycle.webhook(client, remote)).status_code == 200
    assert (await lifecycle.webhook(client, remote)).status_code == 200
    async with SessionLocal() as db:
        assert await db.scalar(select(func.count()).select_from(ListingPromotion)) == 1


async def test_F_G_expiry_and_province_mutation_enforced(client, register_user, provider):
    first_id, first_headers = await target(client, register_user, 'move-top@example.com')
    await purchase(client, provider, first_id, first_headers)
    blocked = await client.patch('/api/v1/listings/' + first_id, headers=first_headers, json={'postcode': '08001'})
    assert blocked.status_code == 409
    pending_id, pending_headers = await target(client, register_user, 'move-pending@example.com')
    assert (await checkout(client, pending_id, pending_headers)).status_code == 200
    blocked = await client.patch('/api/v1/listings/' + pending_id, headers=pending_headers, json={'postcode': '08001'})
    assert blocked.status_code == 409
    third_id, third_headers = await target(client, register_user, 'move-third@example.com')
    await purchase(client, provider, third_id, third_headers)
    before = await availability(client, third_id, third_headers)
    assert before['availableSlots'] == 0
    async with SessionLocal() as db:
        promotion = await db.get(ListingPromotion, UUID(first_id))
        promotion.ends_at = datetime.now(UTC) - timedelta(seconds=1)
        await db.commit()
    after = await availability(client, third_id, third_headers)
    assert after['availableSlots'] == 1


async def test_confirmed_admin_delete_loses_paid_top_without_review(client, register_user, provider):
    listing_id, headers = await target(client, register_user, 'delete-paid@example.com')
    remote = await purchase(client, provider, listing_id, headers)
    admin = await admin_headers(client, register_user)
    removed = await client.delete(f'/api/v1/admin/listings/{listing_id}/promotion', headers=admin)
    assert removed.status_code == 200, removed.text
    async with SessionLocal() as db:
        order = await db.get(PaymentOrder, UUID(remote['client_reference_id']))
        assert await db.get(ListingPromotion, UUID(listing_id)) is None
        assert order.fulfillment_status == 'fulfilled' and order.financial_status == 'normal'
    queue = await client.get('/api/v1/payments/admin/review-required', headers=admin)
    assert queue.status_code == 200 and queue.json() == []
    restore = await client.post(f"/api/v1/payments/admin/orders/{remote['client_reference_id']}/resolve", headers=admin,
                               json={'action': 'restore', 'reason': 'Restore accidentally removed paid TOP'})
    assert restore.status_code == 200 and restore.json()['resolved'] is True
    async with SessionLocal() as db:
        assert await db.get(ListingPromotion, UUID(listing_id)) is None


async def test_confirmed_daily_fulfillment_ignores_new_user_restriction(client, register_user, provider):
    listing_id, headers = await target(client, register_user, 'restricted-paid@example.com')
    result = await checkout(client, listing_id, headers)
    remote = provider[result.json()['url'].rsplit('/', 1)[-1]]
    async with SessionLocal() as db:
        row = await db.get(Listing, UUID(listing_id))
        user = await db.get(User, row.owner_user_id)
        user.blocked = True
        db.add(UserRestriction(user_id=user.id, restriction_type='publish', reason='Audit blocked during payment',
                               starts_at=datetime.now(UTC)))
        await db.commit()
    remote.update(status='complete', payment_status='paid')
    assert (await lifecycle.webhook(client, remote)).status_code == 200
    async with SessionLocal() as db:
        order = await db.get(PaymentOrder, UUID(remote['client_reference_id']))
        assert order.fulfillment_status == 'fulfilled'
        assert await db.get(ListingPromotion, UUID(listing_id)) is not None


async def test_confirmed_admin_shortening_then_normal_financial_event_overbooks(client, register_user, provider, finances):
    listing_id, headers = await target(client, register_user, 'overbook-first@example.com')
    intent, charge, dispute = 'pi_' + uuid4().hex, 'ch_' + uuid4().hex, 'du_' + uuid4().hex
    remote = await purchase(client, provider, listing_id, headers, intent=intent)
    finances[0]['payment_intents/' + intent] = {'id': intent, 'metadata': {'order_id': remote['client_reference_id']}}
    finances[0]['charges/' + charge] = dict(id=charge, payment_intent=intent, amount=3000,
                                          amount_refunded=0, disputed=False, currency='eur', livemode=False)
    finances[0]['disputes/' + dispute] = {'id': dispute, 'charge': charge, 'status': 'won'}
    admin = await admin_headers(client, register_user)
    short_end = datetime.now(UTC) + timedelta(seconds=2)
    shortened = await client.put(f'/api/v1/admin/listings/{listing_id}/promotion', headers=admin,
                                 json={'endsAt': short_end.isoformat()})
    assert shortened.status_code == 200, shortened.text
    await asyncio.sleep(2.1)
    for i in range(3):
        new_id, new_headers = await target(client, register_user, f'overbook-new-{i}@example.com')
        await purchase(client, provider, new_id, new_headers)
    delivered = await audit_helpers.financial_event(client, 'charge.dispute.closed', {'id': dispute, 'charge': charge})
    assert delivered.status_code == 200, delivered.text
    async with SessionLocal() as db:
        count = await db.scalar(select(func.count()).select_from(ListingPromotion).where(
            ListingPromotion.starts_at <= datetime.now(UTC), ListingPromotion.ends_at > datetime.now(UTC)))
        assert count == 4
    search = await client.post('/api/v1/listings/search', json={'rentalMode': 'long', 'provinceCode': '28'})
    assert search.status_code == 200, search.text
    public_promoted = sum(item['promoted'] for item in search.json()['items'])
    assert public_promoted == 4
    evidence = {'head': '15b673864c28ec90c85e78f4cb37eedadfe982c2', 'provinceCode': '28',
                'databaseActiveTopCount': count, 'publicSearchPromotedCount': public_promoted,
                'signedFinancialEventType': 'charge.dispute.closed', 'disputeSnapshotStatus': 'won',
                'adminShortEnd': short_end.isoformat(), 'verifiedAt': datetime.now(UTC).isoformat()}
    (Path(__file__).resolve().parents[1] / 'overbooking-evidence.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print('CONFIRMED: same-province simultaneous TOP count = 4 after normal financial refresh')
