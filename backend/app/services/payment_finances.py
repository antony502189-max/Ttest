"""Authoritative Stripe financial snapshots, durable inbox and operator resolution."""
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert

from ..core.config import get_settings
from ..models.commercial_advertisement import CommercialAdvertisement
from ..models.moderation import HomepageHeroPromotion, ListingPromotion
from ..models.payment_event import PaymentEvent
from ..models.payment_order import PaymentOrder
from .admin import audit
from .catalog import touch_catalog
from .commercial_advertisements import lock_advertising_capacity, require_free_slot
from .stripe_checkout import create_stripe_refund, retrieve_stripe_session, stripe_object

FINANCIAL_EVENTS = {"charge.refunded", "charge.refund.updated", "refund.created", "refund.updated", "refund.failed",
                    "charge.dispute.created", "charge.dispute.updated", "charge.dispute.closed",
                    "charge.dispute.funds_withdrawn", "charge.dispute.funds_reinstated"}


def stripe_id(value, prefix):
    if not isinstance(value, str) or not value.startswith(prefix) or not all(c.isalnum() or c == '_' for c in value):
        raise HTTPException(400, "Invalid Stripe financial identifier")
    return value


async def charge_snapshot(charge_id, *, dispute_id=None):
    charge = await stripe_object("charges/" + stripe_id(charge_id, "ch_"))
    intent_id = stripe_id(charge.get("payment_intent"), "pi_")
    intent = await stripe_object("payment_intents/" + intent_id)
    if charge.get("id") != charge_id or charge.get("currency") != "eur" or charge.get("livemode") is not get_settings().stripe_secret_key.startswith("sk_live_"):
        raise HTTPException(400, "Financial event does not match payment environment")
    receipts, cursor = [], ""
    for _ in range(100):
        batch = await stripe_object("refunds?charge=" + charge_id + "&limit=100" + cursor)
        data = batch.get("data", [])
        receipts.extend(data)
        if not batch.get("has_more"):
            break
        if not data:
            raise HTTPException(502,"Incomplete Stripe refund receipts")
        cursor = "&starting_after=" + stripe_id(data[-1]["id"],"re_")
    else:
        raise HTTPException(409,"Refund history needs manual reconciliation")
    if any(r.get("charge") != charge_id or r.get("currency") != "eur" or type(r.get("amount")) is not int for r in receipts):
        raise HTTPException(400,"Refund receipts do not match charge")
    snapshot = {"intent":intent_id,"charge":charge_id,"amount":charge.get("amount"),
                "refunded":sum(r['amount'] for r in receipts if r.get('status') == 'succeeded'),
                "refundPending":any(r.get('status') in {'pending','requires_action'} for r in receipts),
                "refundFailed":any(r.get('status') in {'failed','canceled'} for r in receipts),
                "disputed":charge.get("disputed", False),
                "orderId":(intent.get("metadata") or {}).get("order_id")}
    if intent.get("id") != intent_id:
        raise HTTPException(400, "Payment intent does not match charge")
    if not snapshot["orderId"]:
        sessions = await stripe_object("checkout/sessions?payment_intent=" + intent_id + "&limit=2")
        matching = sessions.get("data", [])
        if len(matching) == 1:
            snapshot["orderId"] = matching[0].get("client_reference_id")
            snapshot["sessionId"] = matching[0].get("id")
    if dispute_id:
        dispute = await stripe_object("disputes/" + stripe_id(dispute_id, "du_"))
        if dispute.get("charge") != charge_id or dispute.get("id") != dispute_id:
            raise HTTPException(400, "Dispute does not match charge")
        snapshot["disputeStatus"] = dispute["status"]
    return snapshot


async def change_service_finances(order, session):
    """Pause scarce slots without reselling them until the financial result is final."""
    final = order.financial_status in {"refunded", "dispute_lost"}
    normal = order.financial_status == "normal"
    if order.kind == "advertisement":
        ad = await session.get(CommercialAdvertisement, order.target_id)
        if ad and ad.current_payment_order_id == order.id:
            if final:
                ad.payment_status = "refunded" if order.financial_status == "refunded" else "failed"
                ad.status = "cancelled"
            elif not normal:
                if not order.paused_ad_status:
                    order.paused_ad_status = ad.status
                ad.status = "rejected"  # stays reserved, but is no longer publicly shown
            elif order.paused_ad_status:
                await require_free_slot(session, exclude_id=ad.id)
                ad.status = order.paused_ad_status
                order.paused_ad_status = None
    elif order.kind == "homepage_hero":
        hero = await session.get(HomepageHeroPromotion, 1)
        if hero and hero.payment_order_id == order.id and final:
            await session.delete(hero)
    else:
        promotion = await session.get(ListingPromotion, order.target_id)
        baseline_matches = bool(promotion and order.fulfillment_status == "fulfilled" and order.paid_at and promotion.baseline_starts_at and promotion.baseline_ends_at
                                and promotion.baseline_starts_at <= order.paid_at < promotion.baseline_ends_at)
        legacy_matches = bool(promotion and order.fulfillment_status == "fulfilled" and order.paid_at and not promotion.payment_managed and promotion.starts_at <= order.paid_at
                              and (promotion.ends_at is None or order.paid_at < promotion.ends_at))
        if promotion and (legacy_matches or (baseline_matches and not order.service_ends_at)):
            # Old aggregated TOP windows cannot be split safely into purchases.
            # Retain their paid history for explicit, audited restoration/refund.
            promotion.payment_managed = True
            if not order.service_ends_at:
                order.service_starts_at = promotion.baseline_starts_at if baseline_matches else promotion.starts_at
                order.service_ends_at = promotion.baseline_ends_at if baseline_matches else promotion.ends_at
                if baseline_matches:
                    promotion.baseline_starts_at = promotion.baseline_ends_at = None
                others = (await session.scalars(select(PaymentOrder).where(
                    PaymentOrder.target_id == order.target_id, PaymentOrder.kind == "listing_top",
                    PaymentOrder.status == "paid", PaymentOrder.id != order.id,
                    PaymentOrder.financial_status == "normal", PaymentOrder.service_ends_at.is_(None),
                ))).all()
                for other in others:
                    other.fulfillment_status = "review_required"
                    other.fulfillment_note = "Legacy aggregate TOP needs individual entitlement reconciliation."
    if final:
        order.fulfillment_status = "revoked"
        order.resolved_at = order.resolved_at or datetime.now(UTC)
    elif not normal:
        order.fulfillment_status = "review_required"
        order.fulfillment_note = "Financial payment state: " + order.financial_status
    elif order.service_ends_at and order.fulfillment_status == "review_required":
        order.fulfillment_status = "fulfilled"
        order.fulfillment_note = None
    if order.kind == "listing_top":
        promotion = await session.get(ListingPromotion,order.target_id)
        if promotion and promotion.payment_managed:
            remaining = (await session.scalars(select(PaymentOrder).where(
                PaymentOrder.kind == "listing_top",PaymentOrder.target_id == order.target_id,
                PaymentOrder.status == "paid",PaymentOrder.fulfillment_status == "fulfilled",
                PaymentOrder.financial_status == "normal",PaymentOrder.service_ends_at > datetime.now(UTC),
            ))).all()
            starts = [row.service_starts_at for row in remaining if row.service_starts_at]
            ends = [row.service_ends_at for row in remaining]
            if promotion.baseline_ends_at and promotion.baseline_ends_at > datetime.now(UTC):
                starts.append(promotion.baseline_starts_at)
                ends.append(promotion.baseline_ends_at)
            if ends:
                promotion.starts_at, promotion.ends_at = min(starts),max(ends)
                promotion.boosted_at = max(row.paid_at for row in remaining) if remaining else promotion.baseline_starts_at
            else:
                promotion.ends_at = datetime.now(UTC)
            if not promotion.baseline_ends_at:
                promotion.total_price_cents = sum(row.amount_cents for row in remaining)
    await touch_catalog(session)


async def apply_financial_snapshot(snapshot, session):
    await lock_advertising_capacity(session)
    try:
        order_id = UUID(snapshot.get("orderId"))
    except (ValueError, TypeError, AttributeError):
        order_id = None
    order = await session.scalar(select(PaymentOrder).where(or_(
        PaymentOrder.stripe_payment_intent_id == snapshot["intent"], PaymentOrder.id == order_id,
    )).with_for_update().execution_options(populate_existing=True))
    if order is None:
        return None  # The inbox will replay when Checkout delivers its intent ID.
    if type(snapshot["amount"]) is not int or snapshot["amount"] != order.amount_cents or (order.stripe_payment_intent_id and order.stripe_payment_intent_id != snapshot["intent"]) or (snapshot.get("sessionId") and order.stripe_session_id != snapshot["sessionId"]):
        raise HTTPException(400, "Financial event does not match order")
    if type(snapshot["refunded"]) is not int or not 0 <= snapshot["refunded"] <= order.amount_cents:
        raise HTTPException(400, "Invalid refunded amount")
    order.stripe_payment_intent_id, order.stripe_charge_id = snapshot["intent"], snapshot["charge"]
    if snapshot.get("refundStatus") in {"failed", "canceled"} and (snapshot.get("refundId") == order.refund_id or snapshot.get("refundAttempt") == str(order.refund_attempt)):
        order.refund_id = snapshot["refundId"]
        order.financial_status = "refund_failed"
    # Refunds never decrease; event arrival order cannot undo an earlier refund.
    order.refunded_amount_cents = max(order.refunded_amount_cents, snapshot["refunded"])
    if "disputeStatus" in snapshot and order.dispute_status not in {"won", "lost", "warning_closed"}:
        order.dispute_status = snapshot["disputeStatus"]
    if order.refunded_amount_cents >= order.amount_cents:
        order.financial_status = "refunded"
    elif order.dispute_status == "lost":
        order.financial_status = "dispute_lost"
    elif order.dispute_status and order.dispute_status not in {"won", "warning_closed"} or snapshot["disputed"] and order.dispute_status not in {"won", "warning_closed"}:
        order.financial_status = "disputed"
    elif order.refunded_amount_cents:
        order.financial_status = "partial_refund"
    elif snapshot.get("refundPending"):
        order.financial_status = "refund_pending"
    elif snapshot.get("refundFailed") and order.financial_status == "refund_pending":
        order.financial_status = "refund_failed"
    elif order.financial_status not in {"refund_pending", "refund_failed"}:
        order.financial_status = "normal"
    await change_service_finances(order, session)
    return order


async def financial_webhook(event, session):
    if event["type"] not in FINANCIAL_EVENTS:
        return {"received":True}
    event_id = stripe_id(event.get("id"), "evt_")
    if await session.get(PaymentEvent, event_id):
        return {"received":True}
    data = event.get("data")
    obj = data.get("object") if isinstance(data, dict) else None
    if not isinstance(obj, dict):
        raise HTTPException(400, "Invalid Stripe financial event")
    charge_id = obj.get("id") if event["type"] == "charge.refunded" else obj.get("charge")
    # No row/advisory locks or read transaction remain during Stripe GETs.
    await session.commit()
    snapshot = await charge_snapshot(charge_id, dispute_id=obj.get("id") if event["type"].startswith("charge.dispute.") else None)
    if event["type"].startswith("refund.") or event["type"] == "charge.refund.updated":
        refund = await stripe_object("refunds/" + stripe_id(obj.get("id"), "re_"))
        if refund.get("charge") != charge_id:
            raise HTTPException(400,"Refund does not match charge")
        snapshot["refundId"], snapshot["refundStatus"] = refund["id"], refund.get("status")
        snapshot["refundAttempt"] = (refund.get("metadata") or {}).get("attempt")
    # Snapshot is fetched *now*, not trusted from an old/out-of-order webhook.
    inserted = await session.scalar(insert(PaymentEvent).values(id=event_id, payment_intent_id=snapshot["intent"],
        event_type=event["type"],snapshot=snapshot).on_conflict_do_nothing().returning(PaymentEvent.id))
    if inserted:
        applied = await apply_financial_snapshot(snapshot, session)
        if applied:
            receipt = await session.get(PaymentEvent,event_id)
            receipt.applied_at = datetime.now(UTC)
    await session.commit()
    return {"received":True}


async def reconcile_unknown_session(order_id, actor, reason, session_id, session):
    from .payment_fulfillment import apply_stripe_session
    remote = await retrieve_stripe_session(stripe_id(session_id, "cs_"))
    await lock_advertising_capacity(session)
    order = await session.scalar(select(PaymentOrder).where(PaymentOrder.id == order_id).with_for_update().execution_options(populate_existing=True))
    if not order or order.status not in {"creating", "pending"}:
        raise HTTPException(409,"This order does not need Checkout reconciliation")
    if remote.get("client_reference_id") != str(order.id) or remote.get("amount_total") != order.amount_cents or remote.get("currency") != "eur" or remote.get("livemode") is not get_settings().stripe_secret_key.startswith("sk_live_") or (order.stripe_session_id and order.stripe_session_id != session_id):
        raise HTTPException(400,"Payment does not match order")
    order.stripe_session_id, order.checkout_url = session_id, remote.get("url")
    order.status = "pending"
    order.fulfillment_status = "pending"
    order.resolution_actor_id, order.resolution_reason = actor.id, reason
    order.fulfillment_note = None
    session.add(audit(actor.id,"payment.checkout_reconciled","payment",order.id,{"reason":reason,"sessionId":session_id}))
    if remote.get("payment_status") == "paid":
        await apply_stripe_session(remote,"checkout.session.completed",session)
    elif remote.get("status") == "expired":
        await apply_stripe_session(remote,"checkout.session.expired",session)
    else:
        await session.commit()
    return {"resolved":order.status != "creating","status":order.status}


async def replay_financial_inbox(order, session):
    if not order.stripe_payment_intent_id:
        return
    events = (await session.scalars(select(PaymentEvent).where(PaymentEvent.payment_intent_id == order.stripe_payment_intent_id,PaymentEvent.applied_at.is_(None)).order_by(PaymentEvent.received_at))).all()
    for event in events:
        applied = await apply_financial_snapshot(event.snapshot, session)
        if applied:
            event.applied_at = datetime.now(UTC)


async def resolve_payment(order_id, actor, reason, action, session):
    from .payment_fulfillment import apply_stripe_session
    await lock_advertising_capacity(session)
    order = await session.scalar(select(PaymentOrder).where(PaymentOrder.id == order_id).with_for_update().execution_options(populate_existing=True))
    if not order:
        raise HTTPException(404, "Payment order not found")
    if action == "restore":
        if order.fulfillment_status == "fulfilled" and order.financial_status == "normal":
            return {"resolved":True}
        if order.financial_status not in {"normal", "refund_failed"}:
            raise HTTPException(409, "A refund or dispute must be settled before restoration")
        if order.status == "creating" and not order.stripe_session_id:
            raise HTTPException(409, "Unknown Checkout must be reconciled with Stripe before restoration")
        await session.commit()
        remote = await retrieve_stripe_session(order.stripe_session_id)
        if remote.get("payment_status") != "paid":
            raise HTTPException(409, "Stripe has not confirmed payment")
        if remote.get("client_reference_id") != str(order.id) or remote.get("amount_total") != order.amount_cents or remote.get("currency") != "eur" or remote.get("livemode") is not get_settings().stripe_secret_key.startswith("sk_live_") or (order.stripe_payment_intent_id and remote.get("payment_intent") != order.stripe_payment_intent_id):
            raise HTTPException(400,"Payment does not match order")
        if order.financial_status == "refund_failed":
            snapshot = await charge_snapshot(order.stripe_charge_id)
            if snapshot["refunded"] or snapshot.get("refundPending") or (snapshot["disputed"] and order.dispute_status not in {"won","warning_closed"}):
                raise HTTPException(409,"The payment has a refund or dispute")
        await lock_advertising_capacity(session)
        order = await session.scalar(select(PaymentOrder).where(PaymentOrder.id == order_id).with_for_update().execution_options(populate_existing=True))
        if order.financial_status not in {"normal", "refund_failed"}:
            raise HTTPException(409,"Financial state changed; reload the order")
        order.financial_status = "normal"
        order.refund_requested_at = None
        if order.service_ends_at:
            if order.kind != "advertisement":
                from ..models import Listing
                from .homepage_purchase import eligible
                target = await session.get(Listing,order.target_id)
                if not await eligible(target,session):
                    raise HTTPException(409,"The listing is not eligible for restoration")
            if order.kind == "homepage_hero":
                hero = await session.get(HomepageHeroPromotion,1)
                if not hero or hero.payment_order_id != order.id:
                    raise HTTPException(409,"The original homepage period cannot be restored; refund or reconcile")
            elif order.kind == "advertisement":
                ad = await session.get(CommercialAdvertisement,order.target_id)
                if not ad or ad.current_payment_order_id != order.id:
                    raise HTTPException(409,"The original campaign cannot be restored; refund or reconcile")
                from ..models import MediaAsset, User
                owner = await session.get(User,order.owner_user_id)
                image = await session.get(MediaAsset,ad.image_asset_id)
                if not owner or owner.deleted_at or owner.blocked or not image or image.deleted_at:
                    raise HTTPException(409,"The campaign is not eligible for restoration")
            else:
                promotion = await session.get(ListingPromotion,order.target_id)
                if not promotion:
                    session.add(ListingPromotion(listing_id=order.target_id,boosted_at=order.paid_at,
                        starts_at=order.service_starts_at,ends_at=order.service_ends_at,payment_managed=True,
                        total_price_cents=order.amount_cents))
            order.fulfillment_status = "review_required"
            await change_service_finances(order,session)
            order.resolution_actor_id, order.resolution_reason, order.resolved_at = actor.id,reason,datetime.now(UTC)
            session.add(audit(actor.id,"payment.restored","payment",order.id,{"reason":reason,"originalPeriod":True}))
            await session.commit()
            return {"resolved":True}
        await apply_stripe_session(remote, "checkout.session.completed", session, retry=True, actor=actor, reason=reason)
        return {"resolved":order.fulfillment_status == "fulfilled"}
    if order.financial_status == "refunded":
        return {"resolved":True, "financialStatus":"refunded"}
    if order.dispute_status and order.dispute_status not in {"won", "warning_closed"}:
        raise HTTPException(409, "An open or lost dispute cannot be refunded again")
    if order.status != "paid":
        raise HTTPException(409, "Only confirmed paid orders can be refunded")
    if not order.stripe_payment_intent_id:
        await session.commit()
        remote = await retrieve_stripe_session(order.stripe_session_id)
        if remote.get("client_reference_id") != str(order.id) or remote.get("amount_total") != order.amount_cents or remote.get("currency") != "eur" or remote.get("payment_status") != "paid":
            raise HTTPException(400, "Payment does not match order")
        await lock_advertising_capacity(session)
        order = await session.scalar(select(PaymentOrder).where(PaymentOrder.id == order_id).with_for_update().execution_options(populate_existing=True))
        if order.financial_status == "refunded":
            return {"resolved":True,"financialStatus":"refunded"}
        order.stripe_payment_intent_id = stripe_id(remote.get("payment_intent"), "pi_")
    if order.financial_status != "refund_pending":
        order.refund_attempt += 1
        order.refund_id = None
        order.refund_requested_at = datetime.now(UTC)
        order.resolution_actor_id, order.resolution_reason = actor.id, reason
        order.financial_status = "refund_pending"
        session.add(audit(actor.id,"payment.refund_requested","payment",order.id,{"reason":reason,"attempt":order.refund_attempt}))
        await change_service_finances(order, session)
    await session.commit()
    # Recover the provider receipt before retrying POST (including unknown commits).
    if order.refund_id:
        refund = await stripe_object("refunds/" + stripe_id(order.refund_id,"re_"))
    else:
        previous = await stripe_object("refunds?payment_intent=" + stripe_id(order.stripe_payment_intent_id,"pi_") + "&limit=100")
        refund = next((r for r in previous.get("data",[]) if (r.get("metadata") or {}).get("order_id") == str(order.id) and (r.get("metadata") or {}).get("attempt") == str(order.refund_attempt)), None)
        if refund is None:
            if previous.get("has_more") or order.refund_requested_at < datetime.now(UTC)-timedelta(hours=23):
                raise HTTPException(409, "Refund receipt needs manual Stripe reconciliation; do not create another refund")
            refund = await create_stripe_refund(order)
    snapshot = await charge_snapshot(refund["charge"])
    await lock_advertising_capacity(session)
    order = await session.scalar(select(PaymentOrder).where(PaymentOrder.id == order_id).with_for_update().execution_options(populate_existing=True))
    if refund.get("payment_intent") != order.stripe_payment_intent_id or refund.get("currency") != "eur":
        raise HTTPException(400,"Refund does not match order")
    order.refund_id = refund["id"]
    if refund.get("status") in {"failed", "canceled"}:
        order.financial_status = "refund_failed"
        order.fulfillment_note = "Refund failed at Stripe; operator may retry with a new audited attempt."
    await apply_financial_snapshot(snapshot, session)
    session.add(audit(actor.id,"payment.refund_result","payment",order.id,{"refundId":refund["id"],"status":refund.get("status"),"reason":order.resolution_reason}))
    await session.commit()
    return {"resolved":order.financial_status == "refunded","financialStatus":order.financial_status}
