import base64
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from app.api.v1 import commercial_advertisements as advertising_api
from app.api.v1 import payments
from app.schemas.commercial_advertisements import AdvertisementWrite
from app.services import advertising_alerts as alerts
from app.services import commercial_advertisements as ads


@pytest.mark.asyncio
async def test_full_inventory_rejects_before_stripe_and_uses_shared_lock(monkeypatch):
    ad = SimpleNamespace(id=uuid4(), package_id='homepage_1d', status='pending_payment', payment_status='unpaid')
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[ad, None, 7]), execute=AsyncMock())
    provider = AsyncMock()
    monkeypatch.setattr(payments, 'checkout', provider)
    with pytest.raises(HTTPException) as exc:
        await payments.advertisement_checkout(ad.id, SimpleNamespace(id=uuid4()), session)
    assert exc.value.status_code == 409
    assert exc.value.detail == 'No advertising slots available'
    session.execute.assert_awaited_once()
    provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_banner_defaults_to_one_month_at_thirty_euros(monkeypatch):
    ad = SimpleNamespace(id=uuid4(), package_id='homepage_1d', status='pending_payment', payment_status='unpaid')
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[ad, None, 6]), execute=AsyncMock())
    provider = AsyncMock(return_value='checkout')
    monkeypatch.setattr(payments, 'checkout', provider)
    assert await payments.advertisement_checkout(ad.id, SimpleNamespace(id=uuid4()), session) == 'checkout'
    args = provider.await_args.args
    assert args[4:6] == (30, 3000)


@pytest.mark.asyncio
async def test_capacity_counts_paid_review_and_pending_orders_once():
    session = SimpleNamespace(scalar=AsyncMock(return_value=7))
    assert await ads.occupied_slots(session, exclude_id=uuid4()) == 7
    sql = str(session.scalar.await_args.args[0].compile(dialect=postgresql.dialect(), compile_kwargs={'literal_binds': True}))
    assert 'EXISTS' in sql and "payment_orders.status IN ('creating', 'pending')" in sql
    assert "commercial_advertisements.status IN ('pending_review', 'rejected')" in sql
    assert 'commercial_advertisements.id !=' in sql


def test_approval_starts_exactly_one_day_and_legacy_entitlements_survive():
    start = datetime.now(UTC)
    for package, duration in [('homepage_1d', 1), ('test_homepage_30d', 30)]:
        ad = SimpleNamespace(status='pending_review', payment_status='paid', package_id=package,
                             starts_at=None, ends_at=None)
        ads.approve(ad, start, None)
        assert ad.ends_at - ad.starts_at == timedelta(days=duration)


def test_new_writes_cannot_select_future_or_legacy_packages():
    payload = {'title': 'Local service', 'description': 'Local community advertising', 'imageAssetId': uuid4(),
               'destinationType': 'website', 'destination': 'https://example.org/'}
    assert AdvertisementWrite(**payload).packageId == 'homepage_1d'
    with pytest.raises(ValueError):
        AdvertisementWrite(**payload, packageId='test_homepage_30d')


@pytest.mark.asyncio
async def test_public_monthly_advertising_price_matches_server_checkout(monkeypatch):
    monkeypatch.setattr(advertising_api, 'occupied_slots', AsyncMock(return_value=5))
    monkeypatch.setattr(advertising_api, 'get_settings', lambda: SimpleNamespace(web_push_public_key=''))
    monkeypatch.setattr(advertising_api, 'push_configured', lambda: False)
    status = await advertising_api.advertising_availability(SimpleNamespace())
    assert status['monthlyPriceCents'] == ads.PACKAGE_PRICE_CENTS == 3000
    assert status['months'] == 1
    assert status['currency'] == 'EUR'
    assert status['total'] == 7 and status['available'] == 2


def subscription(endpoint='https://fcm.googleapis.com/fcm/send/token'):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    public = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    encode = lambda value: base64.urlsafe_b64encode(value).decode().rstrip('=')
    return {'endpoint': endpoint, 'keys': {'p256dh': encode(public), 'auth': encode(b'x' * 16)}}


@pytest.mark.parametrize('endpoint', ['https://127.0.0.1/push', 'https://fcm.googleapis.com.evil.org/x',
                                    'http://fcm.googleapis.com/x', 'https://fcm.googleapis.com:bad/x',
                                    'https://user:pass@fcm.googleapis.com/x'])
def test_push_rejects_arbitrary_destinations(endpoint):
    with pytest.raises(HTTPException) as exc:
        alerts.validate_subscription(subscription(endpoint))
    assert exc.value.status_code == 422


def test_push_accepts_real_provider_and_validates_keys():
    valid = subscription()
    assert alerts.validate_subscription(valid) == valid
    invalid = subscription()
    invalid['keys']['auth'] = 'malformed'
    with pytest.raises(HTTPException):
        alerts.validate_subscription(invalid)


@pytest.mark.asyncio
async def test_worker_notifies_on_vacancy_and_keeps_completed_payment_reserved(monkeypatch):
    order = SimpleNamespace(stripe_session_id='cs_test', status='pending')
    alert = SimpleNamespace(subscription=None, language='ru', notified_at=None,
                            created_at=datetime.now(UTC), next_attempt_at=None)
    session = SimpleNamespace(execute=AsyncMock(side_effect=[Mock(), Mock(), SimpleNamespace(all=lambda: [(alert, SimpleNamespace(id=uuid4()))])]),
                              scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [order])),
                              scalar=AsyncMock(return_value=alert), flush=AsyncMock(), commit=AsyncMock())
    notify = AsyncMock()
    monkeypatch.setattr(alerts, 'occupied_slots', AsyncMock(return_value=6))
    monkeypatch.setattr(alerts, 'retrieve_stripe_session', AsyncMock(return_value={'status': 'complete'}))
    monkeypatch.setattr(alerts, 'create_notification', notify)
    assert await alerts.process_advertising_alerts(session) == 1
    assert order.status == 'pending'
    assert alert.notified_at is not None
    assert notify.await_args.kwargs['kind'] == 'advertising_slot_available'


@pytest.mark.asyncio
async def test_worker_releases_only_stripe_confirmed_expiry_and_stays_quiet_when_full(monkeypatch):
    order = SimpleNamespace(stripe_session_id='cs_test', status='pending')
    session = SimpleNamespace(execute=AsyncMock(),
                              scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [order])),
                              flush=AsyncMock(), commit=AsyncMock())
    notify = AsyncMock()
    monkeypatch.setattr(alerts, 'occupied_slots', AsyncMock(return_value=7))
    async def confirmed_expiry(*_):
        order.status = 'expired'
    from app.services import payment_fulfillment
    monkeypatch.setattr(payment_fulfillment, 'apply_stripe_session', confirmed_expiry)
    monkeypatch.setattr(alerts, 'retrieve_stripe_session', AsyncMock(return_value={'status': 'expired'}))
    monkeypatch.setattr(alerts, 'create_notification', notify)
    assert await alerts.process_advertising_alerts(session) == 0
    assert order.status == 'expired'
    notify.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('fails', [False, True])
async def test_worker_delivers_push_or_retries_without_losing_subscription(monkeypatch, fails):
    alert = SimpleNamespace(subscription=subscription(), language='en', notified_at=None,
                            created_at=datetime.now(UTC), next_attempt_at=None)
    session = SimpleNamespace(execute=AsyncMock(side_effect=[Mock(), Mock(), SimpleNamespace(all=lambda: [(alert, SimpleNamespace(id=uuid4()))])]),
                              scalars=AsyncMock(return_value=SimpleNamespace(all=list)),
                              scalar=AsyncMock(return_value=alert), flush=AsyncMock(), commit=AsyncMock())
    send = AsyncMock(side_effect=OSError('network unavailable') if fails else None)
    monkeypatch.setattr(alerts, 'occupied_slots', AsyncMock(return_value=6))
    monkeypatch.setattr(alerts, 'create_notification', AsyncMock())
    monkeypatch.setattr(alerts, 'push_configured', lambda: True)
    monkeypatch.setattr(alerts, 'get_settings', lambda: SimpleNamespace(
        web_push_private_key='private', web_push_subject='mailto:hello@example.org', frontend_app_url='https://example.org/site'))
    monkeypatch.setattr(alerts.asyncio, 'to_thread', send)
    assert await alerts.process_advertising_alerts(session) == (0 if fails else 1)
    assert send.await_count == 1
    if fails:
        assert alert.notified_at is None and alert.next_attempt_at is not None
        assert alert.subscription is not None
    else:
        assert alert.notified_at is not None
        assert 'https://example.org/site/#/publicidad/nueva' in send.await_args.kwargs['data']


def test_generated_vapid_keys_can_be_loaded_by_push_library(monkeypatch, tmp_path):
    import sys

    from py_vapid import Vapid

    from app.commands.web_push_keys import main
    output = tmp_path / 'webpush.local.env'
    monkeypatch.setattr(sys, 'argv', ['web_push_keys', '--output', str(output)])
    main()
    values = dict(line.split('=', 1) for line in output.read_text().splitlines())
    loaded = Vapid.from_string(values['WEB_PUSH_PRIVATE_KEY'])
    assert loaded.public_key is not None
    assert len(base64.urlsafe_b64decode(values['WEB_PUSH_PUBLIC_KEY'] + '==')) == 65


@pytest.mark.asyncio
async def test_one_premium_placement_is_exclusive_before_stripe(monkeypatch):
    ad = SimpleNamespace(id=uuid4(), placement="homepage_premium",
                         package_id="homepage_premium_1m", status="pending_payment", payment_status="unpaid")
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[ad, None, 1]), execute=AsyncMock())
    provider = AsyncMock()
    monkeypatch.setattr(payments, "checkout", provider)
    with pytest.raises(HTTPException) as exc:
        await payments.advertisement_checkout(ad.id, SimpleNamespace(id=uuid4()), session)
    assert exc.value.status_code == 409
    assert exc.value.detail == "No advertising slots available"
    provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_premium_checkout_charges_sixty_euros_without_client_price_override(monkeypatch):
    ad = SimpleNamespace(id=uuid4(), placement="homepage_premium",
                         package_id="homepage_premium_1m", status="pending_payment", payment_status="unpaid")
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[ad, None, 0]), execute=AsyncMock())
    provider = AsyncMock(return_value="stripe")
    monkeypatch.setattr(payments, "checkout", provider)
    result = await payments.advertisement_checkout(ad.id, SimpleNamespace(id=uuid4()), session)
    assert result == "stripe"
    assert provider.await_args.args[4:6] == (30, 6000)
    assert provider.await_args.kwargs["months"] == 1


def test_premium_and_standard_are_distinct_valid_packages():
    payload = {'title': 'Banner de negocios', 'description': 'Publicidad comercial local',
               'imageAssetId': uuid4(), 'destinationType': 'website',
               'destination': 'https://example.org/'}
    premium = AdvertisementWrite(**payload, packageId='homepage_premium_1m')
    standard = AdvertisementWrite(**payload)
    assert premium.packageId == 'homepage_premium_1m'
    assert standard.packageId == 'homepage_1d'
    assert ads.placement_for_package(premium.packageId) == "homepage_premium"
    assert ads.placement_for_package(standard.packageId) == "homepage_bottom"
    assert ads.price_for_package(premium.packageId) == 6000
    assert ads.price_for_package(standard.packageId) == 3000
    assert ads.capacity_for_placement("homepage_premium") == 1
    assert ads.capacity_for_placement("homepage_bottom") == 7
    with pytest.raises(ValueError):
        AdvertisementWrite(**payload, packageId='homepage_premium_free')


@pytest.mark.asyncio
async def test_premium_occupancy_filters_only_premium_and_pending_reservations():
    session = SimpleNamespace(scalar=AsyncMock(return_value=1))
    assert await ads.occupied_slots(session, placement="homepage_premium") == 1
    sql = str(session.scalar.await_args.args[0].compile(
        dialect=postgresql.dialect(), compile_kwargs={'literal_binds': True}))
    assert "homepage_premium" in sql
    assert "payment_orders.status IN ('creating', 'pending')" in sql


@pytest.mark.asyncio
async def test_public_availability_offers_separate_verified_prices(monkeypatch):
    monkeypatch.setattr(advertising_api, 'occupied_slots', AsyncMock(side_effect=[3, 0]))
    monkeypatch.setattr(advertising_api, 'get_settings', lambda: SimpleNamespace(web_push_public_key=''))
    monkeypatch.setattr(advertising_api, 'push_configured', lambda: False)
    result = await advertising_api.advertising_availability(SimpleNamespace())
    assert (result['monthlyPriceCents'], result['premiumMonthlyPriceCents']) == (3000, 6000)
    assert (result['available'], result['premiumAvailable']) == (4, 1)
