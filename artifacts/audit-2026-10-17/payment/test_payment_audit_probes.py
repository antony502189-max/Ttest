"""Read-only production-code probes. Persistence/Stripe are isolated test doubles."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.moderation import ListingPromotion
from app.services import admin, payment_finances, payment_fulfillment, payment_sessions, province_top


def paid_pair():
    now = datetime.now(UTC)
    target = uuid4()
    order = NS(id=uuid4(), owner_user_id=uuid4(), target_id=target, kind='listing_top',
               status='paid', fulfillment_status='fulfilled', financial_status='normal',
               paid_at=now, service_starts_at=now, service_ends_at=now + timedelta(days=30),
               amount_cents=3000)
    promotion = NS(listing_id=target, boosted_at=now, starts_at=now,
                   ends_at=order.service_ends_at, payment_managed=True, boosted_by=None,
                   daily_price_cents=100, total_price_cents=3000,
                   baseline_starts_at=None, baseline_ends_at=None)
    return order, promotion


@pytest.mark.asyncio
async def test_admin_can_delete_paid_top_without_order_reconciliation(monkeypatch):
    order, promotion = paid_pair()
    listing, owner, actor = NS(id=order.target_id), NS(id=order.owner_user_id), NS(id=uuid4())
    monkeypatch.setattr(admin, '_actionable_listing', AsyncMock(return_value=(listing, owner)))
    monkeypatch.setattr(admin, 'touch_catalog', AsyncMock())
    monkeypatch.setattr(admin, 'public_listing', lambda *args, **kwargs: {})
    session = NS(scalar=AsyncMock(return_value=promotion), delete=AsyncMock(),
                 commit=AsyncMock(), add=lambda _: None)
    await admin.remove_listing_promotion(listing.id, actor, session)
    session.delete.assert_awaited_once_with(promotion)
    session.commit.assert_awaited_once()
    assert session.scalar.await_count == 1  # No PaymentOrder lookup or financial guard.
    assert order.fulfillment_status == 'fulfilled' and order.financial_status == 'normal'


@pytest.mark.asyncio
async def test_admin_reconfiguration_shortens_paid_window_without_reconciliation(monkeypatch):
    from app.services import commercial_advertisements
    order, promotion = paid_pair()
    listing = NS(id=order.target_id, status='published')
    owner, actor = NS(id=order.owner_user_id), NS(id=uuid4())
    monkeypatch.setattr(commercial_advertisements, 'lock_advertising_capacity', AsyncMock())
    monkeypatch.setattr(province_top, 'require_province_top_slot', AsyncMock())
    monkeypatch.setattr(admin, '_actionable_listing', AsyncMock(return_value=(listing, owner)))
    monkeypatch.setattr(admin, 'require_listing_price', lambda _: None)
    monkeypatch.setattr(admin, 'assert_existing_listing_photo_count', AsyncMock())
    monkeypatch.setattr(admin, 'active_listing_restriction', AsyncMock(return_value=None))
    monkeypatch.setattr(admin, 'active_user_restriction', AsyncMock(return_value=None))
    monkeypatch.setattr(admin, 'touch_catalog', AsyncMock())
    monkeypatch.setattr(admin, 'public_listing', lambda *args, **kwargs: {})
    session = NS(scalar=AsyncMock(return_value=promotion), commit=AsyncMock(), add=lambda _: None)
    new_end = datetime.now(UTC) + timedelta(hours=1)
    await admin.promote_listing(listing.id, actor, session, ends_at=new_end)
    assert promotion.ends_at == new_end < order.service_ends_at
    assert promotion.payment_managed is True
    assert order.fulfillment_status == 'fulfilled'


@pytest.mark.asyncio
async def test_daily_top_fulfillment_skips_current_eligibility(monkeypatch):
    order, _ = paid_pair()
    order.status, order.paid_at = 'pending', None
    order.stripe_session_id, order.stripe_payment_intent_id = 'cs_test_audit_probe', None
    order.days, order.duration_months = 30, None
    # Real eligible() rejects blocked/deleted owner, restriction, missing image,
    # or invalid listing price. The daily purchase branch bypasses it entirely.
    listing = NS(id=order.target_id, status='published', is_external=False, deleted_at=None)
    monkeypatch.setattr(payment_fulfillment, 'eligible', AsyncMock(return_value=False))
    monkeypatch.setattr(payment_fulfillment, 'lock_advertising_capacity', AsyncMock())
    monkeypatch.setattr(payment_fulfillment, 'get_settings', lambda: NS(stripe_secret_key='sk_test_probe'))
    monkeypatch.setattr(payment_fulfillment, 'top_availability', AsyncMock(return_value={'available': True}))
    monkeypatch.setattr(payment_fulfillment, 'touch_catalog', AsyncMock())
    monkeypatch.setattr(payment_fulfillment, 'notify_payment', AsyncMock())
    added = []
    session = NS(scalar=AsyncMock(side_effect=[order, listing, None]), commit=AsyncMock(), add=added.append)
    event = dict(id=order.stripe_session_id, client_reference_id=str(order.id),
                 amount_total=3000, currency='eur', livemode=False, payment_status='paid')
    await payment_fulfillment.apply_stripe_session(event, 'checkout.session.completed', session)
    payment_fulfillment.eligible.assert_not_awaited()
    assert order.fulfillment_status == 'fulfilled'
    assert len(added) == 1 and isinstance(added[0], ListingPromotion)


@pytest.mark.asyncio
async def test_normal_financial_refresh_rebuilds_admin_shortened_paid_window_without_capacity_check(monkeypatch):
    order, promotion = paid_pair()
    promotion.ends_at = datetime.now(UTC) - timedelta(seconds=1)
    monkeypatch.setattr(payment_finances, 'touch_catalog', AsyncMock())
    monkeypatch.setattr(province_top, 'top_availability', AsyncMock(return_value={'available': False}))
    session = NS(get=AsyncMock(return_value=promotion),
                 scalars=AsyncMock(return_value=NS(all=lambda: [order])))
    await payment_finances.change_service_finances(order, session)
    assert promotion.ends_at == order.service_ends_at
    province_top.top_availability.assert_not_awaited()


@pytest.mark.asyncio
async def test_definitively_failed_creation_stays_creating_then_requires_manual_review():
    order = NS(id=uuid4(), checkout_name='TOP', return_path='/mis-anuncios',
               created_at=datetime.now(UTC), status='creating', fulfillment_status='pending')
    session = NS(commit=AsyncMock())
    create = AsyncMock(side_effect=HTTPException(502, 'Could not start Stripe Checkout'))
    with pytest.raises(HTTPException) as failure:
        await payment_sessions.finish_creation(order, session, create=create)
    assert failure.value.status_code == 502 and order.status == 'creating'
    order.created_at = datetime.now(UTC) - timedelta(hours=24)
    with pytest.raises(HTTPException) as failure:
        await payment_sessions.finish_creation(order, session, create=create)
    assert failure.value.status_code == 409
    assert order.status == 'creating' and order.fulfillment_status == 'review_required'
