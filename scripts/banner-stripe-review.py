"""Real Stripe test sessions on the dedicated review DB; never prints secrets."""
import argparse
import asyncio
import hashlib
import json
import os
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

# Read the pre-existing private env file inside the container, never as argv.
for line in Path('/workspace/.stripe-test.secrets').read_text(encoding='utf-8-sig').splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        name, value = line.split('=', 1)
        if name in {'STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET'}:
            os.environ[name] = value.strip().strip('"').strip("'")

from fastapi import HTTPException
from PIL import Image
from sqlalchemy import func, select

from app.api.v1.payments import advertisement_checkout
from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.models import MediaAsset, Notification, User
from app.models.commercial_advertisement import CommercialAdvertisement
from app.models.payment_order import PaymentOrder
from app.services.commercial_advertisements import occupied_slots
from app.services.payment_fulfillment import apply_stripe_session
from app.services.stripe_checkout import expire_stripe_session, retrieve_stripe_session
from app.storage import get_storage

CHECKOUTS = Path('/tmp/banner-review-checkouts.json')


async def main(mode):
    settings = get_settings()
    assert settings.database_url.endswith('/ttest_banner_review_20261014')
    assert settings.stripe_secret_key.startswith('sk_test_') and not settings.stripe_live_payments_enabled
    if mode == 'create':
        async with SessionLocal() as db:
            assert await occupied_slots(db) == 0, 'Review DB must have no reserved slots'
            user = User(email=f'banner-review-{uuid4().hex}@example.org', name='Banner test advertiser', role='host', email_verified=True)
            db.add(user)
            await db.flush()
            output = BytesIO()
            Image.new('RGB', (200, 100), (180, 50, 130)).save(output, 'PNG')
            content = output.getvalue()
            key = f'{user.id}/banner-review-{uuid4().hex}.png'
            get_storage().put(key, content)
            asset = MediaAsset(owner_id=user.id, storage_key=key, kind='advertisement_image', mime_type='image/png',
                               size_bytes=len(content), width=200, height=100, checksum=hashlib.sha256(content).hexdigest())
            db.add(asset)
            await db.flush()
            ads = [CommercialAdvertisement(owner_user_id=user.id, image_asset_id=asset.id, title=f'Banner review {i+1}',
                   description='Dedicated Stripe sandbox banner review.', destination_type='website',
                   destination='https://example.org/', package_id='homepage_1d') for i in range(8)]
            db.add_all(ads)
            await db.commit()
            checkouts = []
            try:
                for ad in ads[:7]:
                    result = await advertisement_checkout(ad.id, user, db)
                    order = await db.scalar(select(PaymentOrder).where(PaymentOrder.target_id == ad.id))
                    checkouts.append({'url': result.url, 'orderId': str(order.id), 'sessionId': order.stripe_session_id})
                    CHECKOUTS.write_text(json.dumps(checkouts))
                    remote = await retrieve_stripe_session(order.stripe_session_id)
                    assert remote['amount_total'] == 100 and remote['currency'] == 'eur' and remote['livemode'] is False
                    assert remote['payment_method_types'] == ['card']
                    assert 30 * 60 <= remote['expires_at'] - remote['created'] <= 35 * 60
                try:
                    await advertisement_checkout(ads[7].id, user, db)
                    raise AssertionError('Eighth real checkout accepted')
                except HTTPException as exc:
                    assert exc.status_code == 409
                repeated = await advertisement_checkout(ads[0].id, user, db)
                assert repeated.url == checkouts[0]['url']
                CHECKOUTS.write_text(json.dumps(checkouts))
                print(json.dumps({'realStripeSessions': len(checkouts), 'amountEachCents': 100, 'eighthRejected': True,
                                  'repeatReused': True, 'mode': 'test', 'paymentsCompleted': 0}))
            except Exception:
                for item in checkouts:
                    expired = await expire_stripe_session(item['sessionId'])
                    await apply_stripe_session(expired, 'checkout.session.expired', db)
                raise
    else:
        if CHECKOUTS.exists():
            checkouts = json.loads(CHECKOUTS.read_text())
        else:
            async with SessionLocal() as db:
                orders = (await db.scalars(select(PaymentOrder).where(PaymentOrder.kind == 'advertisement', PaymentOrder.status == 'pending'))).all()
                checkouts = [{'orderId': str(order.id), 'sessionId': order.stripe_session_id} for order in orders]
        paid = 0
        expired = 0
        async with SessionLocal() as db:
            for item in checkouts:
                remote = await retrieve_stripe_session(item['sessionId'])
                if remote['status'] == 'complete' and remote['payment_status'] == 'paid':
                    await apply_stripe_session(remote, 'checkout.session.completed', db)
                    order = await db.get(PaymentOrder, UUID(item['orderId']))
                    assert order.status == 'paid' and order.fulfillment_status == 'fulfilled'
                    paid += 1
                elif mode == 'cleanup':
                    remote = await expire_stripe_session(item['sessionId'])
                    await apply_stripe_session(remote, 'checkout.session.expired', db)
                    expired += 1
            if mode == 'reconcile':
                ids = [UUID(item['orderId']) for item in checkouts]
                orders = (await db.scalars(select(PaymentOrder).where(PaymentOrder.id.in_(ids)))).all()
                targets = [order.target_id for order in orders]
                banners = await db.scalar(select(func.count(CommercialAdvertisement.id)).where(
                    CommercialAdvertisement.id.in_(targets), CommercialAdvertisement.status == 'pending_review',
                    CommercialAdvertisement.payment_status == 'paid'))
                notifications = await db.scalar(select(func.count(Notification.id)).where(Notification.idempotency_key.in_(
                    [f'payment:{order_id}:advertisement_paid' for order_id in ids])))
                assert paid == banners == notifications == 7
                print(json.dumps({'paidOrders': paid, 'paidBannersAwaitingApproval': banners, 'paymentNotifications': notifications}))
            print(json.dumps({'realStripePaid': paid, 'expiredUnpaidSessions': expired, 'mode': 'test'}))
    await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['create', 'reconcile', 'cleanup'])
    try:
        asyncio.run(main(parser.parse_args().mode))
    except HTTPException as exc:
        response = getattr(exc.__cause__, 'response', None)
        if response is not None:
            error = response.json().get('error', {})
            import re
            message = re.sub(r'(sk_(?:live|test)_|whsec_)[A-Za-z0-9*]+', '[REDACTED]', error.get('message', ''))
            print(json.dumps({'stripeErrorCode': error.get('code'), 'parameter': error.get('param'), 'message': message}))
        raise SystemExit(1) from None
