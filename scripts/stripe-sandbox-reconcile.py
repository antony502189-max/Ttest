"""Recover missed local sandbox events using authenticated Stripe API reads.

The event is real; its delivery and fresh HMAC signature are generated locally.
This is manual reconciliation, NOT evidence of automatic Stripe webhook delivery.
No live keys or databases are accepted. Open/unpaid sessions are left unchanged.
"""
import asyncio
import hashlib
import hmac
import http.client
import json
import time

import httpx
from sqlalchemy import select
from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.models.payment_order import PaymentOrder


async def main():
    settings=get_settings()
    assert settings.database_url.endswith('/ttest_stripe')
    assert settings.stripe_secret_key.startswith('sk_test_') and not settings.stripe_live_payments_enabled
    headers={'Authorization':'Bearer '+settings.stripe_secret_key}
    async with SessionLocal() as db:
        orders=(await db.scalars(select(PaymentOrder).where(PaymentOrder.status=='pending'))).all()
        async with httpx.AsyncClient(timeout=20) as api:
            events=None
            for order in orders:
                if not order.stripe_session_id:
                    continue
                response=await api.get('https://api.stripe.com/v1/checkout/sessions/'+order.stripe_session_id,headers=headers)
                response.raise_for_status()
                obj=response.json()
                assert obj['livemode'] is False
                if obj['payment_status']!='paid':
                    print('UNCHANGED unpaid sandbox order', str(order.id))
                    continue
                assert obj['status']=='complete' and obj['client_reference_id']==str(order.id)
                assert obj['amount_total']==order.amount_cents and obj['currency']=='eur'
                if events is None:
                    response=await api.get('https://api.stripe.com/v1/events',headers=headers,
                        params={'type':'checkout.session.completed','limit':100})
                    response.raise_for_status()
                    events=response.json()['data']
                event=next((event for event in events if event['data']['object']['id']==order.stripe_session_id),None)
                assert event is not None and event['livemode'] is False, 'No matching real sandbox event; use Dashboard'
                # Fetch the original event directly before signing a local replay.
                response=await api.get('https://api.stripe.com/v1/events/'+event['id'],headers=headers)
                response.raise_for_status()
                body=response.content
                for attempt in range(2):
                    timestamp=int(time.time())
                    signature=hmac.new(settings.stripe_webhook_secret.encode(),
                        f'{timestamp}.'.encode()+body, hashlib.sha256).hexdigest()
                    local=http.client.HTTPConnection('127.0.0.1',8000,timeout=10)
                    try:
                        local.request('POST','/api/v1/payments/stripe/webhook',body,
                            {'Content-Type':'application/json','Stripe-Signature':f't={timestamp},v1={signature}'})
                        result=local.getresponse()
                        result.read()
                        assert result.status==200, ('manual_replay_http',result.status)
                    finally:
                        local.close()
                    await db.refresh(order)
                    assert order.status=='paid' and order.paid_at is not None
                    if attempt==0:
                        paid_at=order.paid_at
                    else:
                        assert order.paid_at==paid_at
                print(json.dumps({'operation':'manual local replay of real sandbox event',
                    'eventId':event['id'],'orderId':str(order.id),'amountCents':order.amount_cents,
                    'status':order.status,'paidAt':order.paid_at.isoformat(),'duplicateReplay':'unchanged'}))
    await engine.dispose()


if __name__=='__main__':
    asyncio.run(main())
