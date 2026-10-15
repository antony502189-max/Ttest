"""Synthetic regressions for the combined security and promotion branches."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpcore
import httpx
import pytest
from fastapi import HTTPException

from app.core import public_http
from app.services import payment_finances, stripe_checkout


@pytest.mark.parametrize('address', ['224.0.0.1', '239.255.255.250', 'ff02::1', 'ff0e::1'])
async def test_multicast_dns_answer_never_opens_a_socket(monkeypatch, address):
    monkeypatch.setattr(public_http, 'resolve_host', AsyncMock(return_value={address}))
    connect = AsyncMock()
    monkeypatch.setattr(public_http.AutoBackend, 'connect_tcp', connect)
    with pytest.raises(httpx.ConnectError, match='non-public'):
        await public_http.PublicNetworkBackend().connect_tcp('synthetic.example.test', 443, timeout=1)
    connect.assert_not_awaited()


async def test_connection_dns_remains_bounded_when_client_disables_timeouts(monkeypatch):
    async def resolve(*_):
        await asyncio.sleep(1)
        return {'8.8.8.8'}

    monkeypatch.setattr(public_http, 'PUBLIC_DNS_TIMEOUT_SECONDS', 0.01)
    monkeypatch.setattr(public_http, 'resolve_host', resolve)
    connect = AsyncMock()
    monkeypatch.setattr(public_http.AutoBackend, 'connect_tcp', connect)
    with pytest.raises(httpcore.ConnectTimeout):
        await public_http.PublicNetworkBackend().connect_tcp('synthetic.example.test', 443, timeout=None)
    connect.assert_not_awaited()


def test_oversized_unsigned_webhook_timestamp_is_a_controlled_error(monkeypatch):
    monkeypatch.setattr(stripe_checkout, 'get_settings', lambda: SimpleNamespace(stripe_webhook_secret='whsec_synthetic'))
    with pytest.raises(HTTPException) as error:
        stripe_checkout.verified_stripe_event(b'{}', f't={"9" * 400},v1=invalid')
    assert error.value.status_code == 400


@pytest.mark.parametrize('payload', [None, [], 'invalid', {'id': ['cs_test_bad'], 'url': ['invalid']}])
async def test_malformed_checkout_response_is_502(monkeypatch, payload):
    settings = SimpleNamespace(stripe_secret_key='sk_test_synthetic', stripe_webhook_secret='whsec_synthetic',
                               frontend_app_url='https://frontend.example.test')
    monkeypatch.setattr(stripe_checkout, 'get_settings', lambda: settings)
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload, request=request))
    client = httpx.AsyncClient(transport=transport)
    monkeypatch.setattr(stripe_checkout.httpx, 'AsyncClient', lambda **_: client)
    with pytest.raises(HTTPException) as error:
        await stripe_checkout.create_stripe_session(SimpleNamespace(id=uuid4(), amount_cents=1000), 'TOP', '/mis-anuncios')
    assert error.value.status_code == 502


@pytest.mark.parametrize('data', [None, [], 'invalid'])
async def test_malformed_financial_event_is_rejected_before_provider_io(monkeypatch, data):
    session = SimpleNamespace(get=AsyncMock(return_value=None), commit=AsyncMock())
    provider = AsyncMock()
    monkeypatch.setattr(payment_finances, 'charge_snapshot', provider)
    with pytest.raises(HTTPException) as error:
        await payment_finances.financial_webhook({'id': 'evt_synthetic', 'type': 'charge.refunded', 'data': data}, session)
    assert error.value.status_code == 400
    provider.assert_not_awaited()
    session.commit.assert_not_awaited()
