import logging
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import get_settings
from ...db.session import get_session
from ...models import MediaAsset, User
from ...models.advertising_waitlist import AdvertisingWaitlist
from ...models.commercial_advertisement import CommercialAdvertisement as Ad
from ...models.payment_order import PaymentOrder
from ...schemas.commercial_advertisements import (
    AdvertisementAdminDetail,
    AdvertisementDetail,
    AdvertisementPublic,
    AdvertisementWrite,
    CheckoutResponse,
    DestinationType,
    ModerationDecision,
)
from ...services.advertising_alerts import push_configured, validate_subscription
from ...services.commercial_advertisements import (
    MAX_ACTIVE_HOMEPAGE_ADS,
    PACKAGE_ID,
    PACKAGE_PRICE_CENTS,
    approve,
    assert_advertisement_image_is_unique,
    destination_url,
    lock_advertising_capacity,
    notify_advertiser,
    occupied_slots,
    payment_service,
    require_free_slot,
)
from ...services.listings import mark_orphaned_media
from ...services.media_lifecycle import lock_media_assets, lock_media_owner
from ..dependencies import current_user, require_admin
from .uploads import upload_image

router = APIRouter(tags=["commercial advertisements"])
logger = logging.getLogger(__name__)


def eligible():
    now = func.now()
    return and_(
        Ad.placement == "homepage_bottom", Ad.status == "active", Ad.payment_status.in_(["paid", "waived"]),
        or_(Ad.starts_at.is_(None), Ad.starts_at <= now),
        or_(Ad.ends_at.is_(None), Ad.ends_at > now),
    )


def image_url(asset_id: UUID) -> str:
    return f"/api/v1/media/{asset_id}?variant=card"


def detail(ad: Ad) -> AdvertisementDetail:
    visible_status = "expired" if ad.status in {"active", "pending_review"} and ad.ends_at and ad.ends_at <= datetime.now(UTC) else ad.status
    return AdvertisementDetail(
        id=ad.id, ownerUserId=ad.owner_user_id, title=ad.title, description=ad.description,
        imageAssetId=ad.image_asset_id, imageUrl=image_url(ad.image_asset_id),
        destinationType=cast(DestinationType, ad.destination_type), destination=ad.destination, status=visible_status,
        paymentStatus=ad.payment_status, packageId=ad.package_id, placement=ad.placement,
        createdAt=ad.created_at, startsAt=ad.starts_at, endsAt=ad.ends_at,
        moderationNote=ad.moderation_note,
        paymentOrderId=ad.current_payment_order_id,
    )


async def owned_ad(session: AsyncSession, ad_id: UUID, user: User, *, lock: bool = False) -> Ad:
    query = select(Ad).where(Ad.id == ad_id, Ad.owner_user_id == user.id)
    ad = await session.scalar(query.with_for_update() if lock else query)
    if not ad:
        raise HTTPException(404, "Advertisement not found")
    return ad


async def valid_asset(session: AsyncSession, asset_id: UUID, owner_id: UUID) -> MediaAsset:
    asset = await session.scalar(select(MediaAsset).where(MediaAsset.id == asset_id).with_for_update())
    if not asset or asset.owner_id != owner_id or asset.deleted_at is not None or asset.kind != "advertisement_image" or not asset.mime_type.startswith("image/"):
        raise HTTPException(422, "A valid advertisement image owned by this account is required")
    return asset


@router.get("/advertisements/homepage", response_model=list[AdvertisementPublic])
async def homepage_advertisements(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(
        select(Ad, MediaAsset).join(MediaAsset, Ad.image_asset_id == MediaAsset.id)
        .join(User, Ad.owner_user_id == User.id)
        .where(eligible(), MediaAsset.deleted_at.is_(None), User.deleted_at.is_(None), User.blocked.is_(False))
        .order_by(Ad.admin_priority.desc(), Ad.approved_at, Ad.id).limit(MAX_ACTIVE_HOMEPAGE_ADS)
    )).all()
    return [AdvertisementPublic(
        id=ad.id, title=ad.title, description=ad.description, imageUrl=image_url(ad.image_asset_id),
        imageWidth=asset.width, imageHeight=asset.height, destinationType=cast(DestinationType, ad.destination_type),
        destinationUrl=destination_url(ad.destination_type, ad.destination), placement=ad.placement,
    ) for ad, asset in rows]


@router.get("/advertisements/availability")
async def advertising_availability(session: AsyncSession = Depends(get_session)):
    used = await occupied_slots(session)
    settings = get_settings()
    return {"total": MAX_ACTIVE_HOMEPAGE_ADS, "available": max(0, MAX_ACTIVE_HOMEPAGE_ADS - used),
            "monthlyPriceCents": PACKAGE_PRICE_CENTS, "months": 1, "currency": "EUR", "pushEnabled": push_configured(),
            "pushPublicKey": settings.web_push_public_key if push_configured() else None}


class VacancySubscription(BaseModel):
    subscription: dict | None = None
    language: str = Field(default="es", pattern="^(es|ru|en)$")


@router.post("/advertisements/waitlist")
async def subscribe_advertising_vacancy(
    payload: VacancySubscription, user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
):
    subscription = validate_subscription(payload.subscription) if payload.subscription else None
    if subscription and not push_configured():
        raise HTTPException(503, "Push notifications are not configured")
    await lock_advertising_capacity(session)
    if await occupied_slots(session) < MAX_ACTIVE_HOMEPAGE_ADS:
        return {"subscribed": False, "available": True}
    alert = await session.get(AdvertisingWaitlist, user.id)
    if not alert:
        alert = AdvertisingWaitlist(user_id=user.id)
        session.add(alert)
    elif alert.notified_at is None and alert.subscription == subscription and alert.language == payload.language:
        return {"subscribed": True, "available": False}
    else:
        # Changing a subscription invalidates any in-flight delivery claim.
        alert.created_at = datetime.now(UTC)
    alert.subscription = subscription
    alert.language = payload.language
    alert.notified_at = None
    alert.next_attempt_at = None
    await session.commit()
    return {"subscribed": True, "available": False}


@router.get("/advertisements/waitlist")
async def advertising_waitlist_status(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    alert = await session.get(AdvertisingWaitlist, user.id)
    subscribed = bool(alert and alert.notified_at is None)
    return {"subscribed": subscribed, "channel": "push" if subscribed and alert is not None and alert.subscription else "site"}


@router.delete("/advertisements/waitlist", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe_advertising_vacancy(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await lock_advertising_capacity(session)
    alert = await session.get(AdvertisingWaitlist, user.id)
    if alert:
        await session.delete(alert)
        await session.commit()


@router.post("/advertisements/uploads", status_code=status.HTTP_201_CREATED)
async def upload_advertisement_image(
    file: UploadFile = File(...), user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
):
    uploaded = await upload_image(file=file, user=user, session=session)
    asset = await session.get(MediaAsset, uploaded.id)
    if asset is None:
        raise HTTPException(500, "Uploaded media was not persisted")
    asset.kind = "advertisement_image"
    await session.commit()
    return uploaded.model_copy(update={"kind": "advertisement_image"})


@router.post("/advertisements", response_model=AdvertisementDetail, status_code=status.HTTP_201_CREATED)
async def create_advertisement(
    payload: AdvertisementWrite, user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
):
    return await persist_advertisement(payload, user, session)


@router.post("/admin/advertisements", response_model=AdvertisementDetail, status_code=status.HTTP_201_CREATED)
async def create_admin_advertisement(
    payload: AdvertisementWrite, user: User = Depends(require_admin), session: AsyncSession = Depends(get_session),
):
    return await persist_advertisement(payload, user, session, complimentary=True)


async def persist_advertisement(payload: AdvertisementWrite, user: User, session: AsyncSession, *, complimentary=False):
    await lock_advertising_capacity(session)
    await require_free_slot(session)
    await lock_media_owner(session, user.id)
    created_today = await session.scalar(select(func.count(Ad.id)).where(
        Ad.owner_user_id == user.id, Ad.created_at >= datetime.now(UTC) - timedelta(days=1),
    ))
    if (created_today or 0) >= 20:
        raise HTTPException(429, "Daily advertisement submission limit reached")
    asset = await valid_asset(session, payload.imageAssetId, user.id)
    await assert_advertisement_image_is_unique(session, asset)
    ad = Ad(owner_user_id=user.id, image_asset_id=payload.imageAssetId, title=payload.title,
            description=payload.description, destination_type=payload.destinationType,
            destination=payload.destination, status="pending_payment", payment_status="unpaid",
            placement="homepage_bottom", package_id=payload.packageId, admin_priority=0)
    session.add(ad)
    if complimentary:
        from ...services.homepage_purchase import one_month_after
        now = datetime.now(UTC)
        ad.payment_status = "waived"
        ad.status = "active"
        ad.starts_at, ad.ends_at = now, one_month_after(now)
        ad.approved_at = now
        ad.submitted_at = now
    await session.commit()
    await session.refresh(ad)
    logger.info("commercial_advertisement_created")
    return detail(ad)


@router.get("/advertisements/mine", response_model=list[AdvertisementDetail])
async def my_advertisements(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    ads = (await session.scalars(select(Ad).where(Ad.owner_user_id == user.id).order_by(Ad.created_at.desc()).limit(100))).all()
    issues = set((await session.scalars(select(PaymentOrder.target_id).where(
        PaymentOrder.owner_user_id == user.id, PaymentOrder.kind == "advertisement",
        PaymentOrder.status == "paid", PaymentOrder.fulfillment_status == "review_required",
    ))).all())
    return [detail(ad).model_copy(update={"paymentReviewRequired": ad.id in issues}) for ad in ads]


@router.get("/advertisements/{ad_id}", response_model=AdvertisementDetail)
async def get_advertisement(ad_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    ad = await owned_ad(session, ad_id, user)
    issue = await session.scalar(select(PaymentOrder.id).where(
        PaymentOrder.target_id == ad.id, PaymentOrder.owner_user_id == user.id, PaymentOrder.kind == "advertisement",
        PaymentOrder.status == "paid", PaymentOrder.fulfillment_status == "review_required",
    ).limit(1))
    return detail(ad).model_copy(update={"paymentReviewRequired": issue is not None})


@router.patch("/advertisements/{ad_id}", response_model=AdvertisementDetail)
async def edit_advertisement(
    ad_id: UUID, payload: AdvertisementWrite, user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
):
    await lock_advertising_capacity(session)
    await lock_media_owner(session, user.id)
    current = await owned_ad(session, ad_id, user)
    await lock_media_assets(session, {current.image_asset_id, payload.imageAssetId})
    ad = await owned_ad(session, ad_id, user, lock=True)
    if ad.status == "cancelled":
        raise HTTPException(409, "Cancelled advertisement cannot be edited")
    if ad.current_payment_order_id:
        current_payment = await session.get(PaymentOrder, ad.current_payment_order_id)
        if current_payment and current_payment.financial_status != "normal":
            raise HTTPException(409, "A refund or dispute must be settled before editing")
    asset = await valid_asset(session, payload.imageAssetId, user.id)
    await assert_advertisement_image_is_unique(session, asset, exclude_id=ad.id)
    old_image_id = ad.image_asset_id
    changed = any((ad.title != payload.title, ad.description != payload.description,
                   ad.image_asset_id != payload.imageAssetId, ad.destination_type != payload.destinationType,
                   ad.destination != payload.destination))
    expired = ad.payment_status in {"paid", "waived"} and ad.ends_at is not None and ad.ends_at <= datetime.now(UTC)
    if changed or expired:
        pending = await session.scalar(select(PaymentOrder.id).where(
            PaymentOrder.target_id == ad.id, PaymentOrder.kind == "advertisement",
            PaymentOrder.status.in_(["creating", "pending"]),
        ).limit(1))
        if pending:
            raise HTTPException(409, "Finish or wait for the current payment before editing")
        if ad.payment_status in {"paid", "waived"} and not expired:
            await require_free_slot(session, exclude_id=ad.id)
        ad.title = payload.title
        ad.description = payload.description
        ad.image_asset_id = payload.imageAssetId
        ad.destination_type = payload.destinationType
        ad.destination = payload.destination
        ad.approved_at = None
        if expired:
            ad.payment_status = "unpaid"
            ad.package_id = PACKAGE_ID
            ad.duration_days = None
            ad.current_payment_order_id = None
        # A paid edit keeps its original expiry instead of granting a new day.
        if ad.payment_status not in {"paid", "waived"}:
            ad.starts_at = None
            ad.ends_at = None
        ad.moderation_note = None
        ad.status = "pending_review" if ad.payment_status in {"paid", "waived"} else "pending_payment"
        if ad.status == "pending_review":
            ad.submitted_at = datetime.now(UTC)
        await session.flush()
        if old_image_id != ad.image_asset_id:
            await mark_orphaned_media(session, {old_image_id})
    await session.commit()
    await session.refresh(ad)
    return detail(ad)


@router.delete("/advertisements/{ad_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_advertisement(ad_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await lock_advertising_capacity(session)
    if await session.scalar(select(PaymentOrder.id).where(
        PaymentOrder.target_id == ad_id, PaymentOrder.owner_user_id == user.id,
        PaymentOrder.kind == "advertisement", PaymentOrder.status.in_(["creating", "pending"]),
    ).limit(1)):
        raise HTTPException(409, "Finish or wait for the current payment before editing")
    ad = await owned_ad(session, ad_id, user, lock=True)
    from ...services.payment_guards import protect_payment_deletion
    await protect_payment_deletion(session, target_id=ad.id)
    ad.status = "cancelled"
    await session.commit()


@router.post("/advertisements/{ad_id}/checkout", response_model=CheckoutResponse)
async def advertisement_checkout(ad_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    if get_settings().is_production or get_settings().stripe_secret_key:
        raise HTTPException(404, "Not found")
    ad = await owned_ad(session, ad_id, user)
    display_price = payment_service.checkout(ad)
    return CheckoutResponse(advertisementId=ad.id, packageId=ad.package_id, displayPrice=display_price)


@router.post("/advertisements/{ad_id}/fake-payment/complete", response_model=AdvertisementDetail)
async def complete_test_payment(ad_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    if get_settings().is_production or get_settings().stripe_secret_key:
        raise HTTPException(404, "Not found")
    await lock_advertising_capacity(session)
    await require_free_slot(session, exclude_id=ad_id)
    ad = await owned_ad(session, ad_id, user, lock=True)
    payment_service.complete(ad)
    await session.commit()
    await session.refresh(ad)
    logger.info("commercial_advertisement_test_payment_completed")
    return detail(ad)


@router.get("/admin/advertisements", response_model=list[AdvertisementAdminDetail])
async def admin_advertisements(
    status_filter: str | None = None, user: User = Depends(require_admin), session: AsyncSession = Depends(get_session),
):
    query = select(Ad, User.email).join(User, Ad.owner_user_id == User.id)
    if status_filter == "expired":
        query = query.where(Ad.status == "active", Ad.ends_at <= func.now())
    elif status_filter:
        query = query.where(Ad.status == status_filter)
    rows = (await session.execute(query.order_by(Ad.created_at.desc()).limit(200))).all()
    return [AdvertisementAdminDetail(**detail(ad).model_dump(), ownerEmail=email, adminPriority=ad.admin_priority) for ad, email in rows]


async def admin_ad(session: AsyncSession, ad_id: UUID) -> Ad:
    ad = await session.scalar(select(Ad).where(Ad.id == ad_id).with_for_update())
    if not ad:
        raise HTTPException(404, "Advertisement not found")
    return ad


@router.post("/admin/advertisements/{ad_id}/approve", response_model=AdvertisementDetail)
async def approve_advertisement(
    ad_id: UUID, decision: ModerationDecision, user: User = Depends(require_admin), session: AsyncSession = Depends(get_session),
):
    await lock_advertising_capacity(session)
    ad = await admin_ad(session, ad_id)
    owner_is_active = await session.scalar(
        select(User.id).where(User.id == ad.owner_user_id, User.deleted_at.is_(None), User.blocked.is_(False))
    )
    image_is_active = await session.scalar(
        select(MediaAsset.id).where(
            MediaAsset.id == ad.image_asset_id,
            MediaAsset.owner_id == ad.owner_user_id,
            MediaAsset.deleted_at.is_(None),
            MediaAsset.kind == "advertisement_image",
        )
    )
    if owner_is_active is None or image_is_active is None:
        raise HTTPException(409, "Advertisement owner and image must still be active")
    await require_free_slot(session, exclude_id=ad.id)
    if ad.current_payment_order_id:
        order = await session.get(PaymentOrder, ad.current_payment_order_id)
        if order and order.financial_status != "normal":
            raise HTTPException(409, "A refund or dispute must be settled before approval")
    now = datetime.now(UTC)
    proposed_start = decision.startsAt or ad.starts_at or now
    duration = ad.duration_days or (30 if ad.package_id == "test_homepage_30d" else 1)
    from ...services.homepage_purchase import one_month_after
    paid_order = await session.get(PaymentOrder, ad.current_payment_order_id) if ad.current_payment_order_id else None
    paid_end = one_month_after(proposed_start) if ad.payment_status == "waived" or paid_order and paid_order.duration_months == 1 else proposed_start + timedelta(days=duration)
    proposed_end = decision.endsAt or ad.ends_at or paid_end
    if proposed_start.tzinfo is None or proposed_end.tzinfo is None or proposed_end <= proposed_start or proposed_end <= now:
        raise HTTPException(422, "Invalid advertisement schedule")
    if proposed_end > paid_end:
        raise HTTPException(422, "Advertisement schedule exceeds paid duration")
    overlapping = await session.scalar(
        select(func.count(Ad.id))
        .join(User, User.id == Ad.owner_user_id)
        .join(MediaAsset, MediaAsset.id == Ad.image_asset_id)
        .where(
            Ad.id != ad.id,
            Ad.placement == "homepage_bottom",
            Ad.status == "active",
            Ad.payment_status.in_(["paid", "waived"]),
            or_(Ad.starts_at.is_(None), Ad.starts_at < proposed_end),
            or_(Ad.ends_at.is_(None), Ad.ends_at > proposed_start),
            User.deleted_at.is_(None),
            User.blocked.is_(False),
            MediaAsset.deleted_at.is_(None),
        )
    )
    if (overlapping or 0) >= MAX_ACTIVE_HOMEPAGE_ADS:
        raise HTTPException(409, f"Homepage advertising is limited to {MAX_ACTIVE_HOMEPAGE_ADS} simultaneous campaigns")
    approve(ad, proposed_start, proposed_end)
    if ad.current_payment_order_id:
        order = await session.get(PaymentOrder, ad.current_payment_order_id)
        if order:
            order.service_starts_at, order.service_ends_at = ad.starts_at, ad.ends_at
    await notify_advertiser(session, ad, "advertisement_approved", "Tu publicidad está publicada",
                            "Tu publicidad ha sido aprobada. Puedes consultar su fecha de finalización en Mis campañas.")
    await session.commit()
    await session.refresh(ad)
    logger.info("commercial_advertisement_approved")
    return detail(ad)


@router.post("/admin/advertisements/{ad_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_advertisement(
    ad_id: UUID, decision: ModerationDecision, user: User = Depends(require_admin), session: AsyncSession = Depends(get_session),
):
    await lock_advertising_capacity(session)
    current = await session.get(Ad, ad_id)
    if current is None:
        raise HTTPException(404, "Advertisement not found")
    await lock_media_owner(session, current.owner_user_id)
    await lock_media_assets(session, {current.image_asset_id})
    ad = await admin_ad(session, ad_id)
    if ad.status != "pending_review":
        raise HTTPException(409, "Pending-review advertisement required")
    orders = (await session.scalars(select(PaymentOrder).where(
        PaymentOrder.kind == "advertisement", PaymentOrder.target_id == ad.id,
    ).with_for_update())).all()
    if any(order.status in {"creating", "pending"} for order in orders):
        raise HTTPException(409, "Finish or wait for the current payment before deleting")
    for order in orders:
        if order.status == "paid" and order.financial_status != "refunded":
            order.fulfillment_status = "review_required"
            order.fulfillment_note = "Campaign deleted after moderation rejection; refund required."
    body = f"Tu banner no ha sido aprobado y se ha eliminado.\n\n{ad.title}"
    if decision.note:
        body += f"\n{decision.note}"
    await notify_advertiser(session, ad, "advertisement_deleted", "Tu banner se ha eliminado", body)
    image_id = ad.image_asset_id
    await session.delete(ad)
    await session.flush()
    await mark_orphaned_media(session, {image_id})
    await session.commit()
    logger.info("commercial_advertisement_rejected_and_deleted")


@router.post("/admin/advertisements/{ad_id}/deactivate", response_model=AdvertisementDetail)
async def deactivate_advertisement(
    ad_id: UUID, user: User = Depends(require_admin), session: AsyncSession = Depends(get_session),
):
    await lock_advertising_capacity(session)
    ad = await admin_ad(session, ad_id)
    if ad.status != "active":
        raise HTTPException(409, "Active advertisement required")
    ad.status = "cancelled"
    if ad.current_payment_order_id:
        order = await session.get(PaymentOrder, ad.current_payment_order_id)
        if order and order.status == "paid" and order.financial_status == "normal":
            order.paused_ad_status = "active"
            order.fulfillment_status = "review_required"
            order.fulfillment_note = "Paid campaign was deactivated by moderation; restore or refund."
            ad.payment_status = "paid"
            # Keep its sold capacity until the refund/restore decision.
            ad.status = "rejected"
    await session.commit()
    await session.refresh(ad)
    logger.info("commercial_advertisement_deactivated")
    return detail(ad)
