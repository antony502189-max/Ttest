"""Create a real sandbox TOP checkout through authenticated HTTP, checking a double click.

A short-lived QA auth session is created for an existing LOCAL fixture owner and
revoked in finally. Never prints authentication tokens or API keys.
"""
import asyncio
import http.client
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, exists
from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.session import SessionLocal, engine
from app.models import User, Listing, AuthSession
from app.models.payment_order import PaymentOrder


async def main():
    settings = get_settings()
    assert settings.database_url.endswith('/ttest_stripe')
    assert settings.stripe_secret_key.startswith('sk_test_') and not settings.stripe_live_payments_enabled
    async with SessionLocal() as db:
        pending = await db.scalar(select(PaymentOrder).where(PaymentOrder.kind=='listing_top',
            PaymentOrder.status=='pending', PaymentOrder.days==1).order_by(PaymentOrder.created_at.desc()).limit(1))
        listing = await db.get(Listing, pending.target_id) if pending else None
        if listing is None:
            listing = await db.scalar(select(Listing).join(User, User.id == Listing.owner_user_id).where(
            Listing.status == 'published', Listing.is_external.is_(False), Listing.deleted_at.is_(None),
            User.blocked.is_(False), User.deleted_at.is_(None),
            ~exists().where(PaymentOrder.target_id == Listing.id)))
        assert listing is not None, 'Need a local published listing without an existing payment'
        user = await db.get(User, listing.owner_user_id)
        auth = AuthSession(user_id=user.id, token_hash=uuid4().hex,
                           expires_at=datetime.now(UTC)+timedelta(minutes=10), user_agent='stripe-local-qa')
        db.add(auth)
        await db.commit()
        token = create_access_token(str(user.id), user.role, session_id=str(auth.id))
        def checkout():
            client = http.client.HTTPConnection('127.0.0.1',8000,timeout=30)
            try:
                # Extra client-supplied amount/currency must not control the purchase price.
                client.request('POST', f'/api/v1/payments/listings/{listing.id}/top/checkout',
                    json.dumps({'days':1,'amountCents':1,'currency':'USD','status':'paid'}),
                    {'Content-Type':'application/json','Authorization':'Bearer '+token})
                response=client.getresponse()
                payload=json.loads(response.read())
                assert response.status==200, ('checkout_http',response.status)
                assert payload['amountCents']==100 and payload['currency']=='EUR'
                return payload
            finally:
                client.close()
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(lambda _: checkout(), range(2)))
            assert results[0]['url']==results[1]['url'], 'Double click created different checkouts'
            orders=(await db.scalars(select(PaymentOrder).where(PaymentOrder.target_id==listing.id))).all()
            assert len(orders)==1 and orders[0].amount_cents==100 and orders[0].status=='pending'
            print(json.dumps({'url':results[0]['url'],'listingId':str(listing.id),
                              'orderId':str(orders[0].id),'amountCents':100,
                              'concurrentRequests':2,'persistedOrders':1,'mode':'real-sandbox'}))
        finally:
            auth = await db.get(AuthSession, auth.id)
            auth.revoked_at=datetime.now(UTC)
            await db.commit()
    await engine.dispose()


if __name__=='__main__':
    asyncio.run(main())
