"""Real test-mode checkout evidence on the isolated local Stripe database."""
import asyncio
import hashlib
import http.client
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
from PIL import Image
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.models import Listing, ListingImage, MediaAsset, User
from app.models.commercial_advertisement import CommercialAdvertisement
from app.models.moderation import HomepageHeroPromotion
from app.models.payment_order import PaymentOrder
from app.services.homepage_purchase import one_month_after
from app.services.payment_fulfillment import apply_stripe_session
from app.services.stripe_checkout import retrieve_stripe_session
from app.storage import get_storage

PATH = Path('/tmp/homepage-purchase-evidence.json')


class LocalClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    async def post(self, path, *, headers=None, json=None):
        client = http.client.HTTPConnection('127.0.0.1', 8000, timeout=30)
        try:
            client.request('POST', path, body=__import__('json').dumps(json) if json is not None else None,
                           headers={'Content-Type': 'application/json', **(headers or {})})
            result = client.getresponse()
            return httpx.Response(result.status, content=result.read())
        finally:
            client.close()


async def main(mode):
    settings = get_settings()
    assert settings.database_url.endswith('/ttest_stripe')
    assert settings.stripe_secret_key.startswith('sk_test_') and not settings.stripe_live_payments_enabled
    async with SessionLocal() as db:
        if mode == 'create':
            email = f'homepage-qa-{uuid4().hex[:8]}@example.org'
            password = 'LocalQa-' + uuid4().hex
            owner = User(email=email, name='Marina · Tenerife', role='host', email_verified=True, password_hash=hash_password(password))
            db.add(owner)
            await db.flush()
            source = await db.scalar(select(Listing).where(Listing.status == 'published', Listing.rental_mode == 'long').limit(1))
            assert source is not None
            values = {col.name: getattr(source, col.name) for col in Listing.__table__.columns if col.name not in {'id','owner_user_id','created_at','updated_at'}}
            values.update(title='Habitación luminosa en Costa Adeje', city='Adeje', area='Costa Adeje', monthly_price=550,
                          deleted_at=None, is_external=False, expires_at=None, external_image_urls=[],
                          location='SRID=4326;POINT(-16.7260 28.0902)', exact_location=None)
            listing = Listing(owner_user_id=owner.id, **values)
            db.add(listing)
            photo = Path('/tmp/homepage-room.jpg').read_bytes()
            width, height = Image.open('/tmp/homepage-room.jpg').size
            assets = []
            for kind in ['listing_image', 'advertisement_image']:
                key = f'{owner.id}/homepage-qa-{uuid4().hex}.jpg'
                get_storage().put(key, photo)
                asset = MediaAsset(owner_id=owner.id, storage_key=key, kind=kind, mime_type='image/jpeg',
                                   size_bytes=len(photo), width=width, height=height, checksum=hashlib.sha256(photo).hexdigest())
                db.add(asset)
                await db.flush()
                assets.append(asset)
            db.add(ListingImage(listing_id=listing.id, media_asset_id=assets[0].id, sort_order=0, is_cover=True))
            ad = CommercialAdvertisement(owner_user_id=owner.id, image_asset_id=assets[1].id, title='Tu negocio en Tenerife',
                description='Da a conocer tus servicios a nuestra comunidad.', destination_type='website', destination='https://example.org', package_id='homepage_1d')
            db.add(ad)
            await db.commit()
            async with LocalClient() as client:
                login = await client.post('/api/v1/auth/login', json={'email':email,'password':password})
                assert login.status_code == 200, login.text
                headers = {'Authorization': 'Bearer ' + login.json()['accessToken']}
                route = f'/api/v1/payments/listings/{listing.id}/homepage/checkout'
                first = await client.post(route, headers=headers)
                assert first.status_code == 200, first.text
                repeat = await client.post(route, headers=headers)
                assert repeat.json()['url'] == first.json()['url']
                wrong = await client.post(f'/api/v1/payments/advertisements/{ad.id}/checkout', headers=headers, json={'days':9})
                assert wrong.status_code == 422
                banner = await client.post(f'/api/v1/payments/advertisements/{ad.id}/checkout', headers=headers, json={'days':21,'amountCents':1})
                assert banner.status_code == 200, banner.text
                assert banner.json()['amountCents'] == 2100
                orders = (await db.scalars(select(PaymentOrder).where(PaymentOrder.owner_user_id == owner.id))).all()
                sessions = []
                for order in orders:
                    remote = await retrieve_stripe_session(order.stripe_session_id)
                    assert remote['amount_total'] == order.amount_cents and remote['livemode'] is False
                    sessions.append({'kind':order.kind,'url':order.checkout_url,'sessionId':order.stripe_session_id,'amountCents':order.amount_cents})
                PATH.write_text(json.dumps({'email':email,'password':password,'listingId':str(listing.id),'adId':str(ad.id),'sessions':sessions}))
                print(json.dumps({'realTestCheckouts':len(sessions),'homepageCents':6000,'bannerDays':21,'bannerCents':2100,'repeatReused':True,'minimumRejected':True}))
        else:
            evidence = json.loads(PATH.read_text())
            for item in evidence['sessions']:
                remote = await retrieve_stripe_session(item['sessionId'])
                assert remote['status'] == 'complete' and remote['payment_status'] == 'paid', item['kind']
                await apply_stripe_session(remote, 'checkout.session.completed', db)
                await apply_stripe_session(remote, 'checkout.session.completed', db)
                order = await db.scalar(select(PaymentOrder).where(PaymentOrder.stripe_session_id == item['sessionId']))
                assert order.status == 'paid' and order.fulfillment_status == 'fulfilled'
            hero = await db.get(HomepageHeroPromotion, 1)
            assert str(hero.listing_id) == evidence['listingId']
            assert hero.ends_at == one_month_after(hero.starts_at)
            ad = await db.get(CommercialAdvertisement, __import__('uuid').UUID(evidence['adId']))
            assert ad.duration_days == 21 and ad.status == 'pending_review'
            print(json.dumps({'realPayments':'paid','homepage':'fulfilled','homepageEndsAt':hero.ends_at.isoformat(),'bannerDays':ad.duration_days,'duplicateSafe':True}))
    await engine.dispose()


asyncio.run(main(sys.argv[1]))
