import logging
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...models import MediaAsset, User
from ...models.commercial_advertisement import CommercialAdvertisement as Ad
from ...schemas.commercial_advertisements import (
    AdvertisementAdminDetail,
    AdvertisementDetail,
    AdvertisementPublic,
    AdvertisementWrite,
    CheckoutResponse,
    DestinationType,
    ModerationDecision,
)
from ...services.commercial_advertisements import MAX_ACTIVE_HOMEPAGE_ADS, approve, destination_url, payment_service
from ...services.listings import mark_orphaned_media
from ...services.media_lifecycle import lock_media_assets, lock_media_owner
from ..dependencies import current_user, require_admin
from .uploads import upload_image

router = APIRouter(tags=["commercial advertisements"])
logger = logging.getLogger(__name__)


def eligible():
    now = func.now()
    return and_(
        Ad.placement == "homepage_bottom", Ad.status == "active", Ad.payment_status == "paid",
        or_(Ad.starts_at.is_(None), Ad.starts_at <= now),
        or_(Ad.ends_at.is_(None), Ad.ends_at > now),
    )


def image_url(asset_id: UUID) -> str:
    return f"/api/v1/media/{asset_id}?variant=card"


def detail(ad: Ad) -> AdvertisementDetail:
    visible_status = "expired" if ad.status == "active" and ad.ends_at and ad.ends_at <= datetime.now(UTC) else ad.status
    return AdvertisementDetail(
        id=ad.id, ownerUserId=ad.owner_user_id, title=ad.title, description=ad.description,
        imageAssetId=ad.image_asset_id, imageUrl=image_url(ad.image_asset_id),
        destinationType=cast(DestinationType, ad.destination_type), destination=ad.destination, status=visible_status,
        paymentStatus=ad.payment_status, packageId=ad.package_id, placement=ad.placement,
        createdAt=ad.created_at, startsAt=ad.starts_at, endsAt=ad.ends_at,
        moderationNote=ad.moderation_note,
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
    await lock_media_owner(session, user.id)
    created_today = await session.scalar(select(func.count(Ad.id)).where(
        Ad.owner_user_id == user.id, Ad.created_at >= datetime.now(UTC) - timedelta(days=1),
    ))
    if (created_today or 0) >= 20:
        raise HTTPException(429, "Daily advertisement submission limit reached")
    await valid_asset(session, payload.imageAssetId, user.id)
    ad = Ad(owner_user_id=user.id, image_asset_id=payload.imageAssetId, title=payload.title,
            description=payload.description, destination_type=payload.destinationType,
            destination=payload.destination, status="pending_payment", payment_status="unpaid",
            placement="homepage_bottom", package_id=payload.packageId, admin_priority=0)
    session.add(ad)
    await session.commit()
    await session.refresh(ad)
    logger.info("commercial_advertisement_created")
    return detail(ad)


@router.get("/advertisements/mine", response_model=list[AdvertisementDetail])
async def my_advertisements(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    ads = (await session.scalars(select(Ad).where(Ad.owner_user_id == user.id).order_by(Ad.created_at.desc()).limit(100))).all()
    return [detail(ad) for ad in ads]


@router.get("/advertisements/{ad_id}", response_model=AdvertisementDetail)
async def get_advertisement(ad_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    return detail(await owned_ad(session, ad_id, user))


@router.patch("/advertisements/{ad_id}", response_model=AdvertisementDetail)
async def edit_advertisement(
    ad_id: UUID, payload: AdvertisementWrite, user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
):
    await lock_media_owner(session, user.id)
    current = await owned_ad(session, ad_id, user)
    await lock_media_assets(session, {current.image_asset_id, payload.imageAssetId})
    ad = await owned_ad(session, ad_id, user, lock=True)
    if ad.status == "cancelled":
        raise HTTPException(409, "Cancelled advertisement cannot be edited")
    await valid_asset(session, payload.imageAssetId, user.id)
    old_image_id = ad.image_asset_id
    changed = any((ad.title != payload.title, ad.description != payload.description,
                   ad.image_asset_id != payload.imageAssetId, ad.destination_type != payload.destinationType,
                   ad.destination != payload.destination))
    if changed:
        expired = ad.status == "active" and ad.ends_at is not None and ad.ends_at <= datetime.now(UTC)
        ad.title = payload.title
        ad.description = payload.description
        ad.image_asset_id = payload.imageAssetId
        ad.destination_type = payload.destinationType
        ad.destination = payload.destination
        ad.approved_at = None
        if expired:
            ad.payment_status = "unpaid"
        # Once content changes, the old publication window no longer belongs to
        # the newly moderated creative. A fresh window is assigned on approval.
        ad.starts_at = None
        ad.ends_at = None
        ad.moderation_note = None
        ad.status = "pending_review" if ad.payment_status == "paid" else "pending_payment"
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
    ad = await owned_ad(session, ad_id, user, lock=True)
    ad.status = "cancelled"
    await session.commit()


@router.post("/advertisements/{ad_id}/checkout", response_model=CheckoutResponse)
async def advertisement_checkout(ad_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    ad = await owned_ad(session, ad_id, user)
    display_price = payment_service.checkout(ad)
    return CheckoutResponse(advertisementId=ad.id, packageId=ad.package_id, displayPrice=display_price)


@router.post("/advertisements/{ad_id}/fake-payment/complete", response_model=AdvertisementDetail)
async def complete_test_payment(ad_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
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
    ad = await admin_ad(session, ad_id)
    now = datetime.now(UTC)
    proposed_start = decision.startsAt or ad.starts_at or now
    proposed_end = decision.endsAt or ad.ends_at or proposed_start + timedelta(days=30)
    if proposed_start.tzinfo is None or proposed_end.tzinfo is None or proposed_end <= proposed_start or proposed_end <= now:
        raise HTTPException(422, "Invalid advertisement schedule")
    overlapping = await session.scalar(
        select(func.count(Ad.id)).where(
            Ad.id != ad.id,
            Ad.placement == "homepage_bottom",
            Ad.status == "active",
            Ad.payment_status == "paid",
            or_(Ad.starts_at.is_(None), Ad.starts_at < proposed_end),
            or_(Ad.ends_at.is_(None), Ad.ends_at > proposed_start),
        )
    )
    if (overlapping or 0) >= MAX_ACTIVE_HOMEPAGE_ADS:
        raise HTTPException(409, f"Homepage advertising is limited to {MAX_ACTIVE_HOMEPAGE_ADS} simultaneous campaigns")
    approve(ad, proposed_start, proposed_end)
    await session.commit()
    await session.refresh(ad)
    logger.info("commercial_advertisement_approved")
    return detail(ad)


@router.post("/admin/advertisements/{ad_id}/reject", response_model=AdvertisementDetail)
async def reject_advertisement(
    ad_id: UUID, decision: ModerationDecision, user: User = Depends(require_admin), session: AsyncSession = Depends(get_session),
):
    ad = await admin_ad(session, ad_id)
    if ad.status != "pending_review":
        raise HTTPException(409, "Pending-review advertisement required")
    ad.status = "rejected"
    ad.rejected_at = datetime.now(UTC)
    ad.moderation_note = decision.note
    await session.commit()
    await session.refresh(ad)
    logger.info("commercial_advertisement_rejected")
    return detail(ad)


@router.post("/admin/advertisements/{ad_id}/deactivate", response_model=AdvertisementDetail)
async def deactivate_advertisement(
    ad_id: UUID, user: User = Depends(require_admin), session: AsyncSession = Depends(get_session),
):
    ad = await admin_ad(session, ad_id)
    if ad.status != "active":
        raise HTTPException(409, "Active advertisement required")
    ad.status = "cancelled"
    await session.commit()
    await session.refresh(ad)
    logger.info("commercial_advertisement_deactivated")
    return detail(ad)
