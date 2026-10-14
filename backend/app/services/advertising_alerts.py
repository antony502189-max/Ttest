"""Vacancy detection and durable, one-shot web push delivery."""
import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from fastapi import HTTPException
from sqlalchemy import select

from ..core.config import get_settings
from ..models import User
from ..models.advertising_waitlist import AdvertisingWaitlist
from ..models.payment_order import PaymentOrder
from .commercial_advertisements import MAX_ACTIVE_HOMEPAGE_ADS, lock_advertising_capacity, occupied_slots
from .notifications import create_notification
from .stripe_checkout import retrieve_stripe_session

logger = logging.getLogger(__name__)
COPY = {
    "es": ("Hay un espacio publicitario disponible", "Ya puedes publicar tu publicidad por 30 € al mes."),
    "ru": ("Освободилось место для рекламы", "Теперь можно разместить баннер за 30 € в месяц."),
    "en": ("An advertising slot is available", "You can now place your banner for €30 per month."),
}


def push_configured() -> bool:
    settings = get_settings()
    return bool(settings.web_push_public_key and settings.web_push_private_key and settings.web_push_subject)


def validate_subscription(subscription: dict) -> dict:
    """Accept browser push providers only; never arbitrary outbound URLs."""
    endpoint = subscription.get("endpoint", "")
    if not isinstance(endpoint, str) or len(endpoint) > 2048:
        raise HTTPException(422, "Invalid push subscription")
    try:
        parsed = urlsplit(endpoint)
        host = parsed.hostname or ""
        port = parsed.port
    except ValueError:
        raise HTTPException(422, "Invalid push subscription") from None
    allowed = host in {"fcm.googleapis.com", "updates.push.services.mozilla.com", "web.push.apple.com"}
    allowed = allowed or host.endswith((".push.apple.com", ".notify.windows.com"))
    if (not allowed or parsed.scheme != "https" or parsed.username or parsed.password or port not in {None, 443}
            or parsed.fragment or any(char.isspace() or ord(char) < 32 for char in endpoint)):
        raise HTTPException(422, "Invalid push subscription")
    import base64
    keys = subscription.get("keys")
    if not isinstance(keys, dict):
        raise HTTPException(422, "Invalid push subscription")
    for key, length in (("p256dh", 65), ("auth", 16)):
        try:
            value = keys[key]
            if not isinstance(value, str) or len(value) > 128:
                raise ValueError()
            decoded = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
            if len(decoded) != length:
                raise ValueError()
            if key == "p256dh":
                from cryptography.hazmat.primitives.asymmetric import ec
                ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), decoded)
        except (KeyError, ValueError, TypeError):
            raise HTTPException(422, "Invalid push subscription") from None
    return {"endpoint": endpoint, "keys": {"p256dh": keys["p256dh"], "auth": keys["auth"]}}


async def process_advertising_alerts(session) -> int:
    # Same lock order as checkout, moderation and webhooks; workers may overlap.
    await lock_advertising_capacity(session)
    now = datetime.now(UTC)
    orders = (await session.scalars(select(PaymentOrder).where(
        PaymentOrder.kind.in_(["advertisement", "homepage_hero", "listing_top"]), PaymentOrder.status.in_(["creating", "pending"]),
        PaymentOrder.created_at < now - timedelta(seconds=30),
        PaymentOrder.last_reconciled_at.is_(None) | (PaymentOrder.last_reconciled_at < now - timedelta(seconds=30)),
    ).order_by(PaymentOrder.last_reconciled_at.asc().nulls_first(), PaymentOrder.created_at).limit(2).with_for_update())).all()
    for order in orders:
        order.last_reconciled_at = now
        await session.commit()
        try:
            from .payment_sessions import reconcile_order
            await asyncio.wait_for(reconcile_order(order, session, retrieve=retrieve_stripe_session), timeout=18)
        except (HTTPException, TimeoutError):
            logger.warning("advertising_reservation_reconciliation_failed")
    # Recovery may commit fulfillment. Reacquire capacity before taking claims.
    await lock_advertising_capacity(session)
    await session.flush()
    if await occupied_slots(session) >= MAX_ACTIVE_HOMEPAGE_ADS:
        await session.commit()
        return 0
    rows = (await session.execute(select(AdvertisingWaitlist, User).join(User).where(
        AdvertisingWaitlist.notified_at.is_(None),
        (AdvertisingWaitlist.next_attempt_at.is_(None)) | (AdvertisingWaitlist.next_attempt_at <= now),
        User.deleted_at.is_(None), User.blocked.is_(False),
    ).order_by(AdvertisingWaitlist.created_at).limit(5).with_for_update())).all()
    claimed = []
    for alert, user in rows:
        title, body = COPY.get(alert.language, COPY["es"])
        await create_notification(session, recipient=user, kind="advertising_slot_available",
                                  title=title, body=body,
                                  idempotency_key=f"advertising-vacancy:{alert.created_at.isoformat()}")
        alert.next_attempt_at = now + timedelta(minutes=5)
        claimed.append((user.id, alert.created_at, alert.subscription, title, body))
    # Persist the claim before outbound push calls. Other workers skip claimed
    # subscriptions and checkout never waits on push provider network requests.
    await session.commit()
    delivered = 0
    for user_id, created_at, subscription, title, body in claimed:
        permanent_failure = False
        if subscription:
            if not push_configured():
                continue
            from pywebpush import WebPushException, webpush  # type: ignore[import-untyped]
            settings = get_settings()
            try:
                await asyncio.to_thread(
                    webpush, subscription_info=validate_subscription(subscription),
                    data=json.dumps({"title": title, "body": body,
                                     "url": settings.frontend_app_url.rstrip("/") + "/#/publicidad/nueva"}),
                    vapid_private_key=settings.web_push_private_key,
                    vapid_claims={"sub": settings.web_push_subject}, timeout=5, ttl=300,
                )
            except WebPushException as exc:
                code = exc.response.status_code if exc.response is not None else None
                if code in {404, 410}:
                    permanent_failure = True
                else:
                    logger.warning("advertising_push_retry")
                    continue
            except Exception:  # noqa: BLE001 - Retry unexpected provider failures without losing the durable alert.
                logger.warning("advertising_push_retry")
                continue
        # The user may cancel or rearm while the provider request is in flight.
        alert = await session.scalar(select(AdvertisingWaitlist).where(
            AdvertisingWaitlist.user_id == user_id, AdvertisingWaitlist.created_at == created_at,
            AdvertisingWaitlist.notified_at.is_(None),
            AdvertisingWaitlist.next_attempt_at == now + timedelta(minutes=5),
        ).with_for_update().execution_options(populate_existing=True))
        if alert is None:
            continue
        if permanent_failure:
            alert.subscription = None
        alert.notified_at = now
        delivered += 1
        await session.commit()
    return delivered
