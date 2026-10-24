"""Unit boundaries; unique module name also permits full integration collection."""
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api.v1 import payments
from app.api.v1.payments import BannerCheckoutRequest, TopCheckoutRequest, advertisement_checkout
from app.services import payment_fulfillment as fulfillment
from app.services.homepage_purchase import one_month_after


@pytest.mark.parametrize("start,end", [("2026-01-31", "2026-02-28"), ("2028-01-31", "2028-02-29"), ("2026-12-14", "2027-01-14")])
def test_calendar_month(start, end):
    assert one_month_after(datetime.fromisoformat(start).replace(tzinfo=UTC)).date().isoformat() == end


@pytest.mark.parametrize("hours", [0, 1, 10, 13, 30, 48, 73, 10.5, "12", True])
def test_top_and_homepage_reject_non_tier_duration(hours):
    with pytest.raises(ValidationError):
        TopCheckoutRequest(durationHours=hours)
    with pytest.raises(ValidationError):
        payments.HomepageCheckoutRequest(durationHours=hours)


def test_hourly_prices_are_server_owned_and_homepage_is_exactly_five_times_top():
    from app.services.promotion_offers import amount_cents, offers
    assert offers("listing_top") == [
        {"durationHours": 12, "amountCents": 99},
        {"durationHours": 24, "amountCents": 170},
        {"durationHours": 72, "amountCents": 450},
    ]
    for offer in offers("listing_top"):
        hours = offer["durationHours"]
        assert amount_cents("homepage_hero", hours) == 5 * offer["amountCents"]
        assert TopCheckoutRequest(durationHours=hours).durationHours == hours
        assert payments.HomepageCheckoutRequest(durationHours=hours).durationHours == hours


@pytest.mark.asyncio
@pytest.mark.parametrize("days", [30])
async def test_banner_server_price(monkeypatch, days):
    ad = SimpleNamespace(id=uuid4(), status="pending_payment", payment_status="unpaid", package_id="homepage_1d",
                         placement="homepage_bottom")
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[ad, None]))
    monkeypatch.setattr(payments, "lock_advertising_capacity", AsyncMock())
    monkeypatch.setattr(payments, "require_free_slot", AsyncMock())
    create = AsyncMock()
    monkeypatch.setattr(payments, "checkout", create)
    await advertisement_checkout(ad.id, SimpleNamespace(id=uuid4()), session, BannerCheckoutRequest(days=days))
    assert create.call_args.args[4:6] == (30, 3000)
    assert create.call_args.kwargs['months'] == 1


@pytest.mark.parametrize('days', [10, 21, 31, 30.5, '30', True])
def test_banner_requires_monthly_package(days):
    with pytest.raises(ValidationError):
        BannerCheckoutRequest(days=days)


@pytest.mark.asyncio
@pytest.mark.parametrize("available", [True, False])
async def test_paid_homepage_fulfillment_and_duplicate(monkeypatch, available):
    order = SimpleNamespace(id=uuid4(), target_id=uuid4(), owner_user_id=uuid4(), stripe_session_id="cs_test_homepage",
                            amount_cents=6000, status="pending", kind="homepage_hero", paid_at=None)
    listing = SimpleNamespace(id=order.target_id)
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[order, listing, order]), get=AsyncMock(return_value=None),
                              add=lambda row: added.append(row), commit=AsyncMock())
    added = []
    monkeypatch.setattr(fulfillment, "get_settings", lambda: SimpleNamespace(stripe_secret_key="sk_test_example"))
    monkeypatch.setattr(fulfillment, "lock_advertising_capacity", AsyncMock())
    monkeypatch.setattr(fulfillment, "eligible", AsyncMock(return_value=True))
    monkeypatch.setattr(fulfillment, "slot_available", AsyncMock(return_value=available))
    monkeypatch.setattr(fulfillment, "touch_catalog", AsyncMock())
    monkeypatch.setattr(fulfillment, "notify_payment", AsyncMock())
    remote = {"client_reference_id": str(order.id), "id": order.stripe_session_id, "amount_total": 6000,
              "currency": "eur", "livemode": False, "payment_status": "paid"}
    await fulfillment.apply_stripe_session(remote, "checkout.session.completed", session)
    assert order.fulfillment_status == ("fulfilled" if available else "review_required")
    if available:
        assert added[0].ends_at == one_month_after(order.paid_at)
        assert added[0].listing_id == listing.id
    else:
        assert not added
    await fulfillment.apply_stripe_session(remote, "checkout.session.completed", session)
    assert session.commit.await_count == 1
