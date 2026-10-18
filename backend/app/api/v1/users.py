from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...models import User
from ...models.moderation import ModerationNotice
from ...schemas.auth import AvatarUpdateRequest, UserResponse, UserUpdateRequest
from ...schemas.moderation import ModerationNoticeResponse, MyRestrictionResponse
from ...services.moderation import SUPPORT_EMAIL, active_user_restriction
from ...services.users import delete_account, update_avatar, update_profile
from ..dependencies import authenticated_user, current_user
from .auth import public_user

router = APIRouter(prefix="/users", tags=["users"])


class OwnerAddressRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    street: str = Field(min_length=3, max_length=160)
    postcode: str = Field(pattern=r"^[0-9]{5}$")
    city: str = Field(min_length=2, max_length=120)


@router.get("/me/address")
async def get_owner_address(user: User = Depends(current_user)):
    return {"address": user.verified_address, "verifiedAt": user.address_verified_at}


@router.put("/me/address")
async def set_owner_address(payload: OwnerAddressRequest, user: User = Depends(current_user),
                            session: AsyncSession = Depends(get_session)):
    from ...models import Listing
    from ...models.moderation import ListingPromotion
    from ...models.payment_order import PaymentOrder
    from ...services.address_geography import verify_address
    from ...services.commercial_advertisements import lock_advertising_capacity
    from ...services.province_top import protect_purchased_top
    verified = await verify_address(payload.street, payload.postcode, payload.city)
    await lock_advertising_capacity(session)
    owner = await session.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))
    if not owner or owner.deleted_at or owner.blocked:
        raise HTTPException(404, "User not found")
    if owner.municipality_code != verified.municipality_code:
        owned_ids = (await session.scalars(select(Listing.id).where(Listing.owner_user_id == owner.id))).all()
        first_verification = owner.municipality_code is None and owner.address_verified_at is None
        if first_verification:
            # Bootstrap legacy accounts without moving their existing service.
            # Nullable TOP associations remain blocked until an operator runs
            # the reviewed, capacity-checked backfill. Never overwrite a known
            # historical association using a new unassociated account address.
            known_promotion = await session.scalar(select(ListingPromotion.listing_id).where(
                ListingPromotion.listing_id.in_(owned_ids), ListingPromotion.top_municipality_code.is_not(None),
            ).limit(1))
            known_order = await session.scalar(select(PaymentOrder.id).where(
                PaymentOrder.owner_user_id == owner.id, PaymentOrder.kind == "listing_top",
                PaymentOrder.top_municipality_code.is_not(None),
            ).limit(1))
            if known_promotion or known_order:
                raise HTTPException(409, "Existing TOP municipality association needs operator reconciliation")
        else:
            for listing_id in owned_ids:
                await protect_purchased_top(session, listing_id)
            active = await session.scalar(select(ListingPromotion.listing_id).where(
                ListingPromotion.listing_id.in_(owned_ids),
                (ListingPromotion.ends_at.is_(None)) | (ListingPromotion.ends_at > datetime.now(UTC)),
            ).limit(1))
            if active:
                raise HTTPException(409, "The owner's municipality cannot change while any owned listing has TOP")
    owner.verified_address = verified.private_snapshot()
    owner.municipality_code = verified.municipality_code
    owner.address_verified_at = datetime.now(UTC)
    await session.commit()
    return {"address": owner.verified_address, "verifiedAt": owner.address_verified_at}


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(authenticated_user)):
    return public_user(user)


@router.get("/me/restriction", response_model=MyRestrictionResponse | None)
async def get_my_restriction(
    user: User = Depends(authenticated_user),
    session: AsyncSession = Depends(get_session),
):
    restriction = await active_user_restriction(user.id, session)
    if not restriction:
        return None
    return MyRestrictionResponse(
        restrictionType=restriction.restriction_type,
        reason=restriction.reason,
        until=restriction.ends_at,
        supportEmail=SUPPORT_EMAIL,
    )


@router.get("/me/moderation-notices", response_model=list[ModerationNoticeResponse])
async def get_my_moderation_notices(
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(authenticated_user),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.scalars(
            select(ModerationNotice)
            .where(ModerationNotice.user_id == user.id)
            .order_by(ModerationNotice.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        ModerationNoticeResponse(
            id=row.id,
            kind=row.kind,
            title=row.title,
            body=row.body,
            createdAt=row.created_at,
            readAt=row.read_at,
        )
        for row in rows
    ]


@router.patch("/me/moderation-notices/{notice_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_moderation_notice_read(
    notice_id: UUID,
    user: User = Depends(authenticated_user),
    session: AsyncSession = Depends(get_session),
):
    notice = await session.get(ModerationNotice, notice_id)
    if not notice or notice.user_id != user.id:
        raise HTTPException(404, "Notice not found")
    if notice.read_at is None:
        notice.read_at = datetime.now(UTC)
        await session.commit()


@router.patch("/me", response_model=UserResponse)
async def update_me(
    payload: UserUpdateRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return public_user(await update_profile(payload, user, session))


@router.put("/me/avatar", response_model=UserResponse)
async def update_me_avatar(
    payload: AvatarUpdateRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return public_user(await update_avatar(payload, user, session))


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    response: Response,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await delete_account(user, session)
    response.delete_cookie("refresh_token", path="/api/v1/auth")
