import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import test_banner_payment_lifecycle as lifecycle
import test_payment_audit as audit_helpers
from sqlalchemy import func, select
from test_commercial_advertisements import admin_headers
from test_listing_photo_contract import listing_payload

from app.db.session import SessionLocal
from app.models import Listing, ListingImage, Notification, User
from app.models.moderation import ListingPromotion, UserRestriction
from app.models.payment_order import PaymentOrder

provider = lifecycle.provider
finances = audit_helpers.finances


pytestmark = pytest.mark.integration


async def target(client, register_user, email, postcode='28013'):
    token, _user = await register_user(client, email=email, role='host')
    headers = {'Authorization': 'Bearer ' + token}
    payload = {**listing_payload('Audit remediation Madrid room', []), 'street': 'Calle Mayor 1', 'postcode': '28013',
               'city': 'Madrid', 'latitude': 40.4168, 'longitude': -3.7038}
    response = await client.post('/api/v1/listings', headers=headers, json=payload)
    assert response.status_code == 201, response.text
    verified = await client.put('/api/v1/users/me/address', headers=headers, json={
        'street': 'Calle Mayor 1', 'postcode': '28013' if postcode == '28013' else '28901',
        'city': 'Madrid' if postcode == '28013' else 'Getafe',
    })
    assert verified.status_code == 200, verified.text
    return response.json()['id'], headers


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
    assert other['available'] and other['availableSlots'] == 3 and other['municipalityCode'] == '28065'
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
    for headers in [first_headers, pending_headers]:
        owner_move = await client.put('/api/v1/users/me/address', headers=headers, json={
            'street': 'Calle Mayor 1', 'postcode': '28901', 'city': 'Getafe',
        })
        assert owner_move.status_code == 409, owner_move.text
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


async def test_admin_delete_cannot_lose_paid_top_and_restore_checks_real_projection(client, register_user, provider):
    listing_id, headers = await target(client, register_user, 'delete-paid@example.com')
    remote = await purchase(client, provider, listing_id, headers)
    admin = await admin_headers(client, register_user)
    removed = await client.delete(f'/api/v1/admin/listings/{listing_id}/promotion', headers=admin)
    assert removed.status_code == 409, removed.text
    async with SessionLocal() as db:
        order = await db.get(PaymentOrder, UUID(remote['client_reference_id']))
        assert await db.get(ListingPromotion, UUID(listing_id)) is not None
        assert order.fulfillment_status == 'fulfilled' and order.financial_status == 'normal'
    queue = await client.get('/api/v1/payments/admin/review-required', headers=admin)
    assert queue.status_code == 200 and queue.json() == []
    # Reproduce a missing historical projection independently of the now-protected API.
    async with SessionLocal() as db:
        await db.delete(await db.get(ListingPromotion, UUID(listing_id)))
        await db.commit()
    restore = await client.post(f"/api/v1/payments/admin/orders/{remote['client_reference_id']}/resolve", headers=admin,
                               json={'action': 'restore', 'reason': 'Restore accidentally removed paid TOP'})
    assert restore.status_code == 200 and restore.json()['resolved'] is True
    async with SessionLocal() as db:
        assert await db.get(ListingPromotion, UUID(listing_id)) is not None


@pytest.mark.parametrize('change', ['blocked', 'user_restriction', 'listing_restriction', 'media', 'price'])
async def test_daily_fulfillment_rechecks_eligibility(client, register_user, provider, change):
    listing_id, headers = await target(client, register_user, 'restricted-paid@example.com')
    result = await checkout(client, listing_id, headers)
    remote = provider[result.json()['url'].rsplit('/', 1)[-1]]
    async with SessionLocal() as db:
        row = await db.get(Listing, UUID(listing_id))
        user = await db.get(User, row.owner_user_id)
        if change == 'blocked':
            user.blocked = True
        elif change == 'user_restriction':
            db.add(UserRestriction(user_id=user.id, restriction_type='publish', reason='Changed during checkout', starts_at=datetime.now(UTC)))
        elif change == 'listing_restriction':
            from app.models.moderation import ListingRestriction
            db.add(ListingRestriction(listing_id=row.id, reason='Changed during checkout', starts_at=datetime.now(UTC)))
        elif change == 'media':
            from sqlalchemy import delete
            await db.execute(delete(ListingImage).where(ListingImage.listing_id == row.id))
        else:
            row.monthly_price = 1001
        await db.commit()
    remote.update(status='complete', payment_status='paid')
    assert (await lifecycle.webhook(client, remote)).status_code == 200
    async with SessionLocal() as db:
        order = await db.get(PaymentOrder, UUID(remote['client_reference_id']))
        assert order.fulfillment_status == 'review_required'
        assert await db.get(ListingPromotion, UUID(listing_id)) is None
        assert await db.scalar(select(Notification.id).where(Notification.type == 'payment_review_required'))


async def test_admin_shortening_rejected_and_historical_shortening_cannot_overbook_on_financial_event(client, register_user, provider, finances):
    listing_id, headers = await target(client, register_user, 'overbook-first@example.com')
    intent, charge, dispute = 'pi_' + uuid4().hex, 'ch_' + uuid4().hex, 'du_' + uuid4().hex
    remote = await purchase(client, provider, listing_id, headers, intent=intent)
    finances[0]['payment_intents/' + intent] = {'id': intent, 'metadata': {'order_id': remote['client_reference_id']}}
    finances[0]['charges/' + charge] = {'id': charge, 'payment_intent': intent, 'amount': 3000,
                                          'amount_refunded': 0, 'disputed': False, 'currency': 'eur', 'livemode': False}
    finances[0]['disputes/' + dispute] = {'id': dispute, 'charge': charge, 'status': 'won'}
    admin = await admin_headers(client, register_user)
    short_end = datetime.now(UTC) + timedelta(seconds=2)
    shortened = await client.put(f'/api/v1/admin/listings/{listing_id}/promotion', headers=admin,
                                 json={'endsAt': short_end.isoformat()})
    assert shortened.status_code == 409, shortened.text
    async with SessionLocal() as db:
        promotion = await db.get(ListingPromotion, UUID(listing_id))
        promotion.ends_at = datetime.now(UTC) - timedelta(seconds=1)
        await db.commit()
    for i in range(3):
        new_id, new_headers = await target(client, register_user, f'overbook-new-{i}@example.com')
        await purchase(client, provider, new_id, new_headers)
    delivered = await audit_helpers.financial_event(client, 'charge.dispute.closed', {'id': dispute, 'charge': charge})
    assert delivered.status_code == 200, delivered.text
    async with SessionLocal() as db:
        count = await db.scalar(select(func.count()).select_from(ListingPromotion).where(
            ListingPromotion.starts_at <= datetime.now(UTC), ListingPromotion.ends_at > datetime.now(UTC)))
        assert count == 3
    search = await client.post('/api/v1/listings/search', json={'rentalMode': 'long', 'provinceCode': '28'})
    assert search.status_code == 200, search.text
    public_promoted = sum(item['promoted'] for item in search.json()['items'])
    assert public_promoted == 3
    async with SessionLocal() as db:
        order = await db.get(PaymentOrder, UUID(remote['client_reference_id']))
        assert order.fulfillment_status == 'review_required'
        assert order.service_ends_at > datetime.now(UTC) + timedelta(days=29)
    # Duplicate/out-of-order normal snapshots cannot turn review into a fourth grant.
    assert (await audit_helpers.financial_event(client, 'charge.dispute.closed', {'id': dispute, 'charge': charge})).status_code == 200
    async with SessionLocal() as db:
        assert await db.scalar(select(func.count()).select_from(ListingPromotion).where(ListingPromotion.ends_at > datetime.now(UTC))) == 3


async def test_expiry_during_provider_io_keeps_reservations_and_callbacks_within_three(client, register_user, provider, monkeypatch):
    from app.api.v1 import payments
    old = [await target(client, register_user, f'interleave-old-{i}@example.com') for i in range(2)]
    for listing_id, headers in old:
        await purchase(client, provider, listing_id, headers)
    waiting = await target(client, register_user, 'interleave-waiting@example.com')
    next_buyer = await target(client, register_user, 'interleave-next@example.com')
    entered, release = asyncio.Event(), asyncio.Event()
    create = payments.create_stripe_session

    async def delayed(order, *args):
        if str(order.target_id) == waiting[0]:
            entered.set()
            await release.wait()
        return await create(order, *args)
    monkeypatch.setattr(payments, 'create_stripe_session', delayed)
    task = asyncio.create_task(checkout(client, *waiting))
    await asyncio.wait_for(entered.wait(), timeout=5)
    try:
        assert (await availability(client, *next_buyer))['availableSlots'] == 0
        async with SessionLocal() as db:
            expiry = datetime.now(UTC) - timedelta(seconds=1)
            (await db.get(ListingPromotion, UUID(old[0][0]))).ends_at = expiry
            order = await db.scalar(select(PaymentOrder).where(PaymentOrder.target_id == UUID(old[0][0])))
            order.service_ends_at = expiry
            await db.commit()
        assert (await availability(client, *next_buyer))['availableSlots'] == 1
        await purchase(client, provider, *next_buyer)
    finally:
        release.set()
    started = await asyncio.wait_for(task, timeout=5)
    assert started.status_code == 200, started.text
    remote = provider[started.json()['url'].rsplit('/', 1)[-1]]
    remote.update(status='complete', payment_status='paid')
    assert (await lifecycle.webhook(client, remote)).status_code == 200
    assert (await availability(client, *waiting))['availableSlots'] == 0
    async with SessionLocal() as db:
        assert await db.scalar(select(func.count()).select_from(ListingPromotion).where(ListingPromotion.ends_at > datetime.now(UTC))) == 3


async def test_backfill_refuses_overbooked_owner_associations_without_mutation(client, register_user):
    from app.commands.backfill_geography import backfill
    targets = [await target(client, register_user, f'backfill-{i}@example.com') for i in range(4)]
    async with SessionLocal() as db:
        now = datetime.now(UTC)
        for listing_id, _ in targets:
            db.add(ListingPromotion(listing_id=UUID(listing_id), starts_at=now, boosted_at=now,
                                    ends_at=now + timedelta(days=10)))
        await db.commit()
        report = await backfill(db)
        assert report['capacityConflicts'][0]['occupied'] == 4
        with pytest.raises(ValueError, match='TOP binding refused'):
            await backfill(db, apply=True, bind_top=True)
        await db.rollback()
        assert (await db.scalars(select(ListingPromotion.top_municipality_code))).all() == [None] * 4


async def test_top_survives_new_python_process_and_database_connection(client, register_user, provider):
    import json
    import subprocess
    import sys
    listing_id, headers = await target(client, register_user, 'restart-top@example.com')
    await purchase(client, provider, listing_id, headers)
    script = '''import asyncio,json
from uuid import UUID
from app.db.session import SessionLocal,engine
from app.models import Listing
from app.services.province_top import top_availability
async def check():
 async with SessionLocal() as session:
  listing=await session.get(Listing,UUID(LISTING_ID))
  value=await top_availability(session,listing)
  print(json.dumps({'municipalityCode':value['municipalityCode'],'availableSlots':value['availableSlots']}))
 await engine.dispose()
asyncio.run(check())
'''.replace('LISTING_ID', repr(listing_id))
    result = await asyncio.to_thread(subprocess.run, [sys.executable, '-c', script], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'municipalityCode': '28079', 'availableSlots': 2}


@pytest.mark.parametrize('operation', ['restriction', 'withdraw', 'renew_pending'])
async def test_moderation_of_active_paid_top_enters_review_and_retains_reserved_history(client, register_user, provider, monkeypatch, operation):
    listing_id, headers = await target(client, register_user, 'active-moderation@example.com')
    remote = await purchase(client, provider, listing_id, headers)
    admin = await admin_headers(client, register_user)
    async with SessionLocal() as db:
        original_end = (await db.get(ListingPromotion, UUID(listing_id))).ends_at
    if operation == 'restriction':
        restricted = await client.post(f'/api/v1/admin/listings/{listing_id}/restrictions', headers=admin,
                                       json={'reason': 'Review an active paid listing', 'until': None})
    elif operation == 'withdraw':
        restricted = await client.patch(f'/api/v1/listings/{listing_id}', headers=headers, json={'status': 'hidden'})
    else:
        from app.core.config import get_settings
        monkeypatch.setattr(get_settings(), 'auto_publish_listings', False)
        restricted = await client.post(f'/api/v1/listings/{listing_id}/renew', headers=headers)
    assert restricted.status_code == 200, restricted.text
    async with SessionLocal() as db:
        order = await db.get(PaymentOrder, UUID(remote['client_reference_id']))
        promotion = await db.get(ListingPromotion, UUID(listing_id))
        assert order.fulfillment_status == 'review_required'
        assert order.service_ends_at == promotion.ends_at == original_end
        assert promotion.top_municipality_code == '28079'
    queue = await client.get('/api/v1/payments/admin/review-required', headers=admin)
    assert queue.status_code == 200 and remote['client_reference_id'] in str(queue.json())
