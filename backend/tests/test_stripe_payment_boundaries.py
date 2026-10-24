"""Payment boundary tests: provider calls and persistence are explicitly mocked."""

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1 import payments
from app.core.config import Settings
from app.services import payment_fulfillment, stripe_checkout


def signed_request(event, timestamp=None):
    body = json.dumps(event).encode()
    timestamp = int(time.time()) if timestamp is None else timestamp
    digest = hmac.new(b"whsec_audit", f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return SimpleNamespace(body=AsyncMock(return_value=body)), f"t={timestamp},v1={digest}"


@pytest.fixture
def configured(monkeypatch):
    settings = SimpleNamespace(stripe_secret_key="sk_test_audit", stripe_webhook_secret="whsec_audit")
    monkeypatch.setattr(payments, "get_settings", lambda: settings)
    monkeypatch.setattr(payments, "lock_advertising_capacity", AsyncMock())
    monkeypatch.setattr(payment_fulfillment, "get_settings", lambda: settings)
    monkeypatch.setattr(payment_fulfillment, "lock_advertising_capacity", AsyncMock())
    monkeypatch.setattr(payment_fulfillment, "notify_payment", AsyncMock())
    monkeypatch.setattr(payment_fulfillment, "eligible", AsyncMock(return_value=True))
    monkeypatch.setattr(payment_fulfillment, "touch_catalog", AsyncMock())
    monkeypatch.setattr(stripe_checkout, "get_settings", lambda: settings)
    monkeypatch.setattr(payments, "retrieve_stripe_session", AsyncMock(return_value={"status":"open"}))


@pytest.mark.parametrize("event", [[], None, "invalid", {}, {"type": 1}])
def test_signed_invalid_json_structure_is_400(configured, event):
    request, signature = signed_request(event)
    with pytest.raises(HTTPException) as error:
        stripe_checkout.verified_stripe_event(request.body.return_value, signature)
    assert error.value.status_code == 400


def test_expired_signature_is_rejected(configured):
    request, signature = signed_request({"type": "test"}, int(time.time()) - 600)
    with pytest.raises(HTTPException) as error:
        stripe_checkout.verified_stripe_event(request.body.return_value, signature)
    assert error.value.status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize("data", [None, [], {"object": None}, {"object": []}])
async def test_invalid_checkout_event_is_400(configured, data):
    request, signature = signed_request({"type": "checkout.session.completed", "data": data})
    session = SimpleNamespace(scalar=AsyncMock(), commit=AsyncMock())
    with pytest.raises(HTTPException) as error:
        await payments.stripe_webhook(request, signature, session)
    assert error.value.status_code == 400
    session.commit.assert_not_awaited()


def order_event(kind="advertisement"):
    order = SimpleNamespace(id=uuid4(), owner_user_id=uuid4(), target_id=uuid4(),
                            kind=kind, top_municipality_code="28079", stripe_session_id="cs_test_audit", status="pending",
                            amount_cents=3000 if kind == "advertisement" else 100, days=1, paid_at=None)
    obj = {"id": order.stripe_session_id, "client_reference_id": str(order.id),
           "amount_total": order.amount_cents, "currency": "eur", "livemode": False,
           "payment_status": "paid"}
    return order, {"type": "checkout.session.completed", "data": {"object": obj}}


@pytest.mark.asyncio
@pytest.mark.parametrize("key,value", [("amount_total", 1), ("currency", "usd"),
                                     ("livemode", True), ("id", "cs_test_other"),
                                     ("client_reference_id", "invalid")])
async def test_payment_mismatch_is_rejected(configured, key, value):
    order, event = order_event()
    event["data"]["object"][key] = value
    session = SimpleNamespace(scalar=AsyncMock(return_value=order), commit=AsyncMock())
    request, signature = signed_request(event)
    with pytest.raises(HTTPException) as error:
        await payments.stripe_webhook(request, signature, session)
    assert error.value.status_code == 400
    assert order.status == "pending"
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_unpaid_completion_does_not_grant_service(configured):
    order, event = order_event()
    event["data"]["object"]["payment_status"] = "unpaid"
    session = SimpleNamespace(scalar=AsyncMock(), commit=AsyncMock())
    request, signature = signed_request(event)
    assert await payments.stripe_webhook(request, signature, session) == {"received": True}
    session.scalar.assert_not_awaited()
    assert order.status == "pending"


@pytest.mark.asyncio
async def test_ad_payment_and_duplicate_webhook(configured):
    order, event = order_event()
    ad = SimpleNamespace(id=order.target_id, package_id="homepage_1d", placement="homepage_bottom",
                         status="pending_payment", payment_status="unpaid", submitted_at=None)
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[order, ad, 0, order]), commit=AsyncMock())
    request, signature = signed_request(event)
    await payments.stripe_webhook(request, signature, session)
    assert (order.status, ad.status, ad.payment_status) == ("paid", "pending_review", "paid")
    paid_at = order.paid_at
    await payments.stripe_webhook(request, signature, session)
    assert order.paid_at == paid_at
    assert session.commit.await_count == 1


@pytest.mark.asyncio
async def test_top_records_initial_total_and_duplicate_is_ignored(configured, monkeypatch):
    monkeypatch.setattr(payment_fulfillment, "top_availability", AsyncMock(return_value={"available": True}))
    order, event = order_event("listing_top")
    listing = SimpleNamespace(status="published", is_external=False, deleted_at=None, id=order.target_id)
    added = []
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[order, listing, None, order]),
                              commit=AsyncMock(), add=added.append, get=AsyncMock(return_value=SimpleNamespace(address_verified_at=datetime.now(UTC), municipality_code="28079")))
    request, signature = signed_request(event)
    await payments.stripe_webhook(request, signature, session)
    assert len(added) == 1
    promotion = added[0]
    assert promotion.total_price_cents == 100
    assert (promotion.ends_at - promotion.starts_at).days == 1
    await payments.stripe_webhook(request, signature, session)
    assert len(added) == 1
    assert session.commit.await_count == 1


@pytest.mark.asyncio
async def test_late_top_payment_cannot_displace_three_province_slots(configured, monkeypatch):
    monkeypatch.setattr(payment_fulfillment, "top_availability", AsyncMock(return_value={"available": False}))
    order, event = order_event("listing_top")
    listing = SimpleNamespace(status="published", is_external=False, deleted_at=None, id=order.target_id)
    added = []
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[order, listing]), commit=AsyncMock(), add=added.append, get=AsyncMock(return_value=SimpleNamespace(address_verified_at=datetime.now(UTC), municipality_code="28079")))
    request, signature = signed_request(event)
    await payments.stripe_webhook(request, signature, session)
    assert order.status == "paid"
    assert order.fulfillment_status == "review_required"
    assert added == []


@pytest.mark.asyncio
async def test_pending_checkout_is_reused(configured, monkeypatch):
    user = SimpleNamespace(id=uuid4())
    previous = SimpleNamespace(checkout_url="https://checkout.stripe.com/test", days=1,
                               stripe_session_id="cs_test_audit", amount_cents=100, created_at=datetime.now(UTC))
    session = SimpleNamespace(scalar=AsyncMock(return_value=previous), commit=AsyncMock())
    provider = AsyncMock()
    monkeypatch.setattr(payments, "create_stripe_session", provider)
    result = await payments.checkout(session, user, "listing_top", uuid4(), 1, 100, "TOP", "/mis-anuncios")
    assert result.url == previous.checkout_url
    provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_different_package_during_pending_checkout_is_conflict(configured):
    previous = SimpleNamespace(checkout_url="https://checkout.stripe.com/test", days=1,
                               stripe_session_id="cs_test_audit", amount_cents=100, created_at=datetime.now(UTC))
    session = SimpleNamespace(scalar=AsyncMock(return_value=previous), commit=AsyncMock())
    with pytest.raises(HTTPException) as error:
        await payments.checkout(session, SimpleNamespace(id=uuid4()), "listing_top", uuid4(),
                                7, 500, "TOP", "/mis-anuncios")
    assert error.value.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize("initial,expected,commits", [("pending", "expired", 1),
                                                    ("paid", "paid", 0), ("expired", "expired", 0)])
async def test_expiry_is_idempotent_and_never_downgrades_paid(configured, initial, expected, commits):
    order, event = order_event()
    order.status = initial
    event["type"] = "checkout.session.expired"
    event["data"]["object"]["payment_status"] = "unpaid"
    session = SimpleNamespace(scalar=AsyncMock(return_value=order), commit=AsyncMock())
    request, signature = signed_request(event)
    await payments.stripe_webhook(request, signature, session)
    await payments.stripe_webhook(request, signature, session)
    assert order.status == expected and session.commit.await_count == commits


def test_live_key_requires_explicit_enablement():
    settings = Settings(_env_file=None, app_env="development", stripe_secret_key="sk_live_audit",
                        stripe_webhook_secret="whsec_audit", stripe_live_payments_enabled=False)
    with pytest.raises(RuntimeError, match="Live Stripe payments require"):
        settings.validate_runtime()


@pytest.mark.asyncio
async def test_completed_session_blocks_another_charge(configured, monkeypatch):
    previous = SimpleNamespace(checkout_url="https://checkout.stripe.com/test", stripe_session_id="cs_test_audit")
    session = SimpleNamespace(scalar=AsyncMock(return_value=previous), commit=AsyncMock())
    monkeypatch.setattr(payments, "retrieve_stripe_session", AsyncMock(return_value={"status":"complete"}))
    provider = AsyncMock()
    monkeypatch.setattr(payments, "create_stripe_session", provider)
    with pytest.raises(HTTPException) as error:
        await payments.checkout(session, SimpleNamespace(id=uuid4()), "listing_top", uuid4(), 1, 100,
                                "TOP", "/mis-anuncios")
    assert error.value.status_code == 409
    provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_provider_outage_does_not_create_another_charge(configured, monkeypatch):
    previous = SimpleNamespace(checkout_url="https://checkout.stripe.com/test", stripe_session_id="cs_test_audit")
    session = SimpleNamespace(scalar=AsyncMock(return_value=previous), commit=AsyncMock())
    monkeypatch.setattr(payments, "retrieve_stripe_session", AsyncMock(side_effect=HTTPException(502)))
    provider = AsyncMock()
    monkeypatch.setattr(payments, "create_stripe_session", provider)
    with pytest.raises(HTTPException) as error:
        await payments.checkout(session, SimpleNamespace(id=uuid4()), "listing_top", uuid4(), 1, 100,
                                "TOP", "/mis-anuncios")
    assert error.value.status_code == 502
    provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_expired_provider_session_can_be_replaced(configured, monkeypatch):
    monkeypatch.setattr(payments, "require_province_top_slot", AsyncMock())
    previous = SimpleNamespace(checkout_url="https://checkout.stripe.com/test", stripe_session_id="cs_test_old",
                               status="pending")
    session = SimpleNamespace(scalar=AsyncMock(return_value=previous), get=AsyncMock(), add=lambda _: None,
                              flush=AsyncMock(), commit=AsyncMock())
    monkeypatch.setattr(payments, "retrieve_stripe_session", AsyncMock(return_value={"status":"expired"}))
    monkeypatch.setattr(payments, "create_stripe_session", AsyncMock(return_value=("cs_test_new", "https://checkout.stripe.com/new")))
    async def expire(*_):
        previous.status = "expired"
    monkeypatch.setattr(payments, "apply_stripe_session", expire)
    monkeypatch.setattr(payments, "finish_creation", AsyncMock(return_value="https://checkout.stripe.com/new"))
    result = await payments.checkout(session, SimpleNamespace(id=uuid4(), municipality_code="28079"), "listing_top", uuid4(), 1, 100,
                                    "TOP", "/mis-anuncios")
    assert result.url == "https://checkout.stripe.com/new" and previous.status == "expired"
