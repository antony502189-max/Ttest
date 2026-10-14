"""Purchase and verify one €30 calendar-month TOP in the local Stripe sandbox."""
import asyncio
import http.client
import json
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.models.moderation import ListingPromotion
from app.models.payment_order import PaymentOrder
from app.services.homepage_purchase import one_month_after
from app.services.payment_fulfillment import apply_stripe_session
from app.services.stripe_checkout import retrieve_stripe_session


def request(path, payload, headers=None):
    client = http.client.HTTPConnection('127.0.0.1', 8000, timeout=30)
    try:
        client.request('POST', path, json.dumps(payload), {'Content-Type':'application/json', **(headers or {})})
        response = client.getresponse()
        body = json.loads(response.read())
        assert response.status == 200, (response.status, body)
        return body
    finally:
        client.close()


async def main(mode):
    settings = get_settings()
    assert settings.database_url.endswith('/ttest_stripe')
    assert settings.stripe_secret_key.startswith('sk_test_') and not settings.stripe_live_payments_enabled
    evidence = json.loads(Path('/tmp/homepage-purchase-evidence.json').read_text())
    async with SessionLocal() as db:
        if mode == 'create':
            login = request('/api/v1/auth/login', {'email':evidence['email'], 'password':evidence['password']})
            headers = {'Authorization':'Bearer ' + login['accessToken']}
            route = f"/api/v1/payments/listings/{evidence['listingId']}/top/checkout"
            result = request(route, {'days':30, 'amountCents':1}, headers)
            assert result['amountCents'] == 3000
            assert request(route, {'days':30}, headers)['url'] == result['url']
            order = await db.scalar(select(PaymentOrder).where(
                PaymentOrder.target_id == UUID(evidence['listingId']), PaymentOrder.kind == 'listing_top', PaymentOrder.status == 'pending'))
            remote = await retrieve_stripe_session(order.stripe_session_id)
            assert remote['amount_total'] == 3000 and remote['livemode'] is False and order.duration_months == 1
            evidence['top'] = {'url':result['url'], 'sessionId':order.stripe_session_id}
            Path('/tmp/monthly-top-evidence.json').write_text(json.dumps(evidence))
            print(json.dumps({'testCheckout':True,'amountCents':3000,'months':1,'repeatReused':True}))
        else:
            evidence = json.loads(Path('/tmp/monthly-top-evidence.json').read_text())
            remote = await retrieve_stripe_session(evidence['top']['sessionId'])
            assert remote['status'] == 'complete' and remote['payment_status'] == 'paid'
            await apply_stripe_session(remote, 'checkout.session.completed', db)
            promotion = await db.get(ListingPromotion, UUID(evidence['listingId']))
            original_end = promotion.ends_at
            await apply_stripe_session(remote, 'checkout.session.completed', db)
            assert promotion.ends_at == original_end == one_month_after(promotion.starts_at)
            print(json.dumps({'payment':'paid','top':'active','amountCents':3000,'endsAt':original_end.isoformat(),'duplicateSafe':True}))
    await engine.dispose()


asyncio.run(main(sys.argv[1]))
