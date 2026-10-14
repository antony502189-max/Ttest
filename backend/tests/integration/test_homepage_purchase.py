import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from test_banner_payment_lifecycle import provider, webhook
from test_listing_photo_contract import listing_payload
from test_commercial_advertisements import admin_headers, create_ad
from app.db.session import SessionLocal
from app.models.moderation import HomepageHeroPromotion
from app.services.homepage_purchase import one_month_after

pytestmark = pytest.mark.integration


async def listing(client, register_user, email):
    token, _ = await register_user(client, email=email, role='host')
    headers = {'Authorization': 'Bearer ' + token}
    response = await client.post('/api/v1/listings', headers=headers, json=listing_payload('Paid homepage test', []))
    assert response.status_code == 201, response.text
    return response.json()['id'], headers


async def test_single_slot_race_fulfillment_and_expiry(client, register_user, provider):
    first, owner = await listing(client, register_user, 'homepage-first@example.com')
    second, other = await listing(client, register_user, 'homepage-second@example.com')
    results = await asyncio.gather(
        client.post(f'/api/v1/payments/listings/{first}/homepage/checkout', headers=owner),
        client.post(f'/api/v1/payments/listings/{second}/homepage/checkout', headers=other),
    )
    assert sorted(result.status_code for result in results) == [200, 409]
    index = next(i for i, result in enumerate(results) if result.status_code == 200)
    winner, headers = [(first, owner), (second, other)][index]
    result = results[index]
    assert result.json()['amountCents'] == 6000 and len(provider) == 1
    repeat = await client.post(f'/api/v1/payments/listings/{winner}/homepage/checkout', headers=headers)
    assert repeat.json()['url'] == result.json()['url']
    remote = provider[result.json()['url'].rsplit('/', 1)[-1]]
    remote.update(status='complete', payment_status='paid')
    assert (await webhook(client, remote)).status_code == 200
    assert (await webhook(client, remote)).status_code == 200
    public = await client.get('/api/v1/listings/homepage-hero')
    assert public.json()['id'] == winner
    async with SessionLocal() as db:
        hero = await db.get(HomepageHeroPromotion, 1)
        assert hero.ends_at == one_month_after(hero.starts_at)
        starts, ends = hero.starts_at, hero.ends_at
    admin = await admin_headers(client, register_user)
    denied = await client.delete('/api/v1/admin/homepage-hero', headers=admin)
    assert denied.status_code == 409
    async with SessionLocal() as db:
        hero = await db.get(HomepageHeroPromotion, 1)
        assert (hero.starts_at, hero.ends_at) == (starts, ends)
        hero.ends_at = datetime.now(UTC) - timedelta(seconds=1)
        await db.commit()
    assert (await client.get('/api/v1/listings/homepage-hero')).json() is None
    assert (await client.get('/api/v1/payments/homepage/quote', headers=other)).json()['available']


async def test_cancel_releases_homepage_reservation(client, register_user, provider):
    target, headers = await listing(client, register_user, 'homepage-cancel@example.com')
    response = await client.post(f'/api/v1/payments/listings/{target}/homepage/checkout', headers=headers)
    assert response.status_code == 200
    assert not (await client.get('/api/v1/payments/homepage/quote', headers=headers)).json()['available']
    cancelled = await client.post(f'/api/v1/payments/listings/{target}/homepage/checkout/cancel', headers=headers)
    assert cancelled.json()['cancelled']
    assert (await client.get('/api/v1/payments/homepage/quote', headers=headers)).json()['available']
    assert (await client.get('/api/v1/listings/homepage-hero')).json() is None


async def test_monthly_banner_quote_and_approved_duration(client, register_user, provider):
    ad, _, headers, _ = await create_ad(client, register_user, 'banner-duration@example.com')
    route = '/api/v1/payments/advertisements/' + ad['id']
    for invalid in [9, 10, 21, 31, 10.5, 366]:
        assert (await client.post(route + '/checkout', headers=headers, json={'days': invalid})).status_code == 422
    quote = await client.get(route + '/quote', headers=headers)
    assert quote.json()['amountCents'] == 3000 and quote.json()['months'] == 1
    result = await client.post(route + '/checkout', headers=headers, json={'days': 30, 'amountCents': 1})
    assert result.status_code == 200 and result.json()['amountCents'] == 3000
    assert (await client.get(route + '/quote', headers=headers)).json()['reservedDays'] == 30
    changed = await client.post(route + '/checkout', headers=headers, json={'days': 10})
    assert changed.status_code == 422
    remote = provider[result.json()['url'].rsplit('/', 1)[-1]]
    remote.update(status='complete', payment_status='paid')
    assert (await webhook(client, remote)).status_code == 200
    admin = await admin_headers(client, register_user)
    approved = await client.post('/api/v1/admin/advertisements/' + ad['id'] + '/approve', headers=admin, json={})
    assert approved.status_code == 200, approved.text
    value = approved.json()
    assert datetime.fromisoformat(value['endsAt']) == one_month_after(datetime.fromisoformat(value['startsAt']))
