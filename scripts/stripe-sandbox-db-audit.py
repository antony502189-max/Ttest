"""Run inside the isolated sandbox backend. All synthetic changes are rolled back.

This exercises real PostgreSQL persistence with synthetic, locally signed events;
it does NOT make payments or prove delivery from Stripe.
"""

import asyncio
import hashlib
import hmac
import http.client
import json
import time
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.api.v1.payments import advertisement_checkout, listing_top_checkout, stripe_webhook, TopCheckoutRequest
from app.core.config import get_settings
from app.db.session import engine
from app.models import Listing, User
from app.models.commercial_advertisement import CommercialAdvertisement
from app.models.moderation import ListingPromotion
from app.models.payment_order import PaymentOrder


async def deliver(session, order, **changes):
    obj = dict(id=order.stripe_session_id, client_reference_id=str(order.id),
               payment_status="paid", amount_total=order.amount_cents, currency="eur", livemode=False)
    obj.update(changes)
    body = json.dumps({"type": "checkout.session.completed", "data": {"object": obj}}).encode()
    timestamp = int(time.time())
    digest = hmac.new(get_settings().stripe_webhook_secret.encode(),
                      f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return await stripe_webhook(Request({"type": "http"}, receive), f"t={timestamp},v1={digest}", session)


async def main():
    settings = get_settings()
    assert settings.database_url.endswith("/ttest_stripe"), "Use the isolated sandbox DB only"
    assert settings.stripe_secret_key.startswith("sk_test_") and not settings.stripe_live_payments_enabled
    async with engine.connect() as connection:
        outer = await connection.begin()
        try:
            async with AsyncSession(bind=connection, expire_on_commit=False,
                                    join_transaction_mode="create_savepoint") as session:
                ad = await session.scalar(select(CommercialAdvertisement).where(
                    CommercialAdvertisement.status == "pending_payment"))
                assert ad is not None, "Need a local unpaid advertisement fixture"
                owner = await session.get(User, ad.owner_user_id)
                other = await session.scalar(select(User).where(User.id != owner.id))
                try:
                    await advertisement_checkout(ad.id, other, session)
                    raise AssertionError("Foreign advertisement accepted")
                except HTTPException as error:
                    assert error.status_code == 404
                print("PASS real_db: foreign advertisement rejected before provider call")
                listing = await session.scalar(select(Listing).where(Listing.status == "published",
                    Listing.is_external.is_(False), Listing.deleted_at.is_(None)))
                assert listing is not None
                other_listing_user = await session.scalar(select(User).where(User.id != listing.owner_user_id))
                try:
                    await listing_top_checkout(listing.id, TopCheckoutRequest(days=1), other_listing_user, session)
                    raise AssertionError("Foreign listing accepted")
                except HTTPException as error:
                    assert error.status_code == 404
                print("PASS real_db: foreign listing rejected before provider call")
                order = PaymentOrder(owner_user_id=owner.id, kind="advertisement", target_id=ad.id,
                    days=30, amount_cents=3000, status="pending", stripe_session_id="cs_test_audit_"+uuid4().hex)
                session.add(order)
                await session.flush()
                for key, value in [("amount_total", 1), ("currency", "usd"), ("livemode", True)]:
                    try:
                        await deliver(session, order, **{key:value})
                        raise AssertionError("Mismatched payment accepted")
                    except HTTPException as error:
                        assert error.status_code == 400 and order.status == "pending"
                print("PASS real_db: amount, currency and live-mode mismatch rejected")
                await deliver(session, order, payment_status="unpaid")
                assert order.status == "pending" and ad.payment_status == "unpaid"
                print("PASS real_db: unpaid completion grants no service")
                await deliver(session, order)
                await session.refresh(order)
                await session.refresh(ad)
                assert order.status == "paid" and ad.payment_status == "paid" and ad.status == "pending_review"
                paid_at = order.paid_at
                await deliver(session, order)
                await session.refresh(order)
                assert order.paid_at == paid_at
                print("PASS real_db: paid advertisement persisted; repeated event is idempotent")
                # A fixture-specific promotion is removed only inside the rollback transaction.
                promotion = await session.get(ListingPromotion, listing.id)
                if promotion:
                    await session.delete(promotion)
                    await session.flush()
                top = PaymentOrder(owner_user_id=listing.owner_user_id, kind="listing_top", target_id=listing.id,
                    days=7, amount_cents=500, status="pending", stripe_session_id="cs_test_audit_"+uuid4().hex)
                session.add(top)
                await session.flush()
                await deliver(session, top)
                promotion = await session.get(ListingPromotion, listing.id)
                assert promotion.total_price_cents == 500 and (promotion.ends_at-promotion.starts_at).days == 7
                ends_at = promotion.ends_at
                await deliver(session, top)
                await session.refresh(promotion)
                assert promotion.ends_at == ends_at and promotion.total_price_cents == 500
                print("PASS real_db: TOP persisted with total; duplicate adds no extra days")
        finally:
            await outer.rollback()
            print("ROLLBACK complete: synthetic changes not retained")
    # The app intentionally patches httpx to block outbound private-network URLs.
    # Use the stdlib for these explicit loopback-only diagnostic requests.
    for path, body, expected in [
        ("/api/v1/payments/stripe/webhook", {"type":"checkout.session.completed"}, 400),
        (f"/api/v1/payments/listings/{uuid4()}/top/checkout", {"days":1}, 401),
    ]:
        client = http.client.HTTPConnection("127.0.0.1", 8000, timeout=10)
        try:
            client.request("POST", path, json.dumps(body), {"Content-Type":"application/json"})
            response = client.getresponse()
            response.read()
            assert response.status == expected, (path, response.status)
            print(f"PASS real_http: {path} => {expected}")
        finally:
            client.close()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
