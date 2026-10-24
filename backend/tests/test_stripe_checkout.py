import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException

from app.services import stripe_checkout


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,path,separator", [
    ("advertisement", "/publicidad/123/checkout", "?"),
    ("homepage_hero", "/mis-anuncios?homepage=123", "&"),
])
async def test_checkout_returns_to_hash_routes(monkeypatch, kind, path, separator):
    captured = {}
    requests = []

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, url, *, data, headers):
            captured.update(data)
            requests.append((dict(data), dict(headers)))
            assert url == "https://api.stripe.com/v1/checkout/sessions"
            assert headers["Authorization"] == "Bearer sk_test_example"
            return httpx.Response(200, json={"id": "cs_test_example", "url": "https://checkout.stripe.com/test"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(stripe_checkout, "get_settings", lambda: SimpleNamespace(
        stripe_secret_key="sk_test_example", stripe_webhook_secret="whsec_example",
        frontend_app_url="http://localhost:5173/",
    ))
    monkeypatch.setattr(stripe_checkout.httpx, "AsyncClient", lambda **_: Client())
    order = SimpleNamespace(id=uuid4(), amount_cents=3000, kind=kind, created_at=datetime.now(UTC))
    session_id, checkout_url = await stripe_checkout.create_stripe_session(order, "Banner", path)

    assert (session_id, checkout_url) == ("cs_test_example", "https://checkout.stripe.com/test")
    assert captured["success_url"] == f"http://localhost:5173/#{path}{separator}payment=return"
    assert captured["cancel_url"] == f"http://localhost:5173/#{path}{separator}payment=cancelled"
    assert captured["line_items[0][price_data][unit_amount]"] == "3000"
    assert captured["payment_method_types[0]"] == "card"
    assert "allowed_payment_method_types[0]" not in captured
    assert int(captured["expires_at"]) == int(order.created_at.timestamp()) + 3600
    assert requests[0][1]['Stripe-Version'] == '2025-06-30.basil'
    monkeypatch.setattr(stripe_checkout.time, 'time', lambda: order.created_at.timestamp() + 120)
    await stripe_checkout.create_stripe_session(order, "Banner", path)
    assert requests[0] == requests[1]


def test_webhook_signature_rejects_tampering(monkeypatch):
    monkeypatch.setattr(stripe_checkout, "get_settings", lambda: SimpleNamespace(stripe_webhook_secret="whsec_example"))
    body = json.dumps({"type": "checkout.session.completed"}).encode()
    timestamp = int(time.time())
    signature = hmac.new(b"whsec_example", f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()

    assert stripe_checkout.verified_stripe_event(body, f"t={timestamp},v1={signature}")["type"] == "checkout.session.completed"
    with pytest.raises(HTTPException) as error:
        stripe_checkout.verified_stripe_event(body + b" ", f"t={timestamp},v1={signature}")
    assert error.value.status_code == 400
