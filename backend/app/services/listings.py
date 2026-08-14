from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..models import DiscardedListing, Favorite, Listing, ListingImage, ListingStatusHistory, User
from ..models.room_details import ListingRoomDetails
from ..repositories.listings import owned_query, owned_response_from, point
from ..schemas.listings import (
    ListingImageResponse,
    ListingImagesRequest,
    ListingPatch,
    ListingWrite,
    OwnedListingResponse,
)
from .catalog import touch_catalog
from .media_lifecycle import lock_media_assets
from .moderation import enforce_publish_access, is_admin
from .storage_deletions import enqueue_storage_deletions

ROOM_DETAIL_MAPPING = {
    "homeSizeM2": "home_size_m2",
    "bathroomCount": "bathroom_count",
    "rentalUnit": "rental_unit",
    "bedType": "bed_type",
    "bedCount": "bed_count",
    "currentRoomResidents": "current_room_residents",
    "toilet": "toilet",
    "householdGender": "household_gender",
    "householdHasChildren": "household_has_children",
    "heatingType": "heating_type",
    "accessible": "accessible",
    "couplesAllowed": "couples_allowed",
    "acceptedTenantTypes": "accepted_tenant_types",
}


async def ensure_owner_or_admin(listing: Listing, user: User, session: AsyncSession) -> bool:
    """Authorize a listing mutation using the server-side admin allowlist.

    The legacy product role is not an authorization boundary: once admin access
    is revoked in `admin_access`, cross-owner listing capabilities disappear
    immediately even if an older account still carries role="admin".
    """
    admin = await is_admin(user, session)
    if listing.owner_user_id != user.id and not admin:
        raise HTTPException(403, "Forbidden")
    return admin


async def mark_orphaned_media(session: AsyncSession, candidate_ids: set[UUID]) -> int:
    locked_assets = await lock_media_assets(session, candidate_ids)
    active_assets = {asset.id: asset for asset in locked_assets if asset.deleted_at is None}
    active_ids = set(active_assets)
    if not active_ids:
        return 0
    attached = set(
        (
            await session.scalars(
                select(ListingImage.media_asset_id).where(ListingImage.media_asset_id.in_(active_ids))
            )
        ).all()
    )
    avatars = {
        value
        for value in (
            await session.scalars(select(User.avatar_asset_id).where(User.avatar_asset_id.in_(active_ids)))
        ).all()
        if value is not None
    }
    orphan_ids = active_ids - attached - avatars
    assets = [active_assets[asset_id] for asset_id in sorted(orphan_ids, key=str)]
    if not assets:
        return 0
    now = datetime.now(UTC)
    for asset in assets:
        asset.deleted_at = now
    await enqueue_storage_deletions(session, {asset.storage_key for asset in assets})
    return len(assets)


def apply_write(listing: Listing, payload: ListingWrite) -> None:
    listing.title = payload.title
    listing.city = payload.city
    listing.area = payload.area
    listing.street = payload.street
    listing.postcode = payload.postcode
    listing.approximate_address = payload.approximateAddress
    listing.rental_mode = payload.rentalMode
    listing.monthly_price = payload.monthlyPrice
    listing.nightly_price = payload.nightlyPrice
    listing.weekly_price = payload.weeklyPrice
    listing.room_type = payload.roomType
    listing.available_from = payload.availableFrom
    listing.available_until = payload.availableUntil
    listing.minimum_stay_months = payload.minimumStayMonths
    listing.minimum_nights = payload.minimumNights
    listing.deposit_amount = payload.depositAmount
    listing.bills_included = payload.billsIncluded
    listing.bathroom = payload.bathroom
    listing.kitchen = payload.kitchen
    listing.furnished = payload.furnished
    listing.room_size_m2 = payload.roomSizeM2
    listing.bedroom_count = payload.bedroomCount
    listing.current_residents = payload.currentResidents
    listing.room_capacity = payload.roomCapacity
    listing.shower = payload.shower
    listing.tenant_requirement = payload.tenantRequirement
    listing.smoking_allowed = payload.smokingAllowed
    listing.pets_allowed = payload.petsAllowed
    listing.children_allowed = payload.childrenAllowed
    listing.empadronamiento_allowed = payload.empadronamientoAllowed
    listing.restrictions = payload.restrictions
    listing.amenities = payload.amenities
    listing.location = point(payload.longitude, payload.latitude)
    listing.exact_location = (
        point(payload.exactLongitude, payload.exactLatitude)
        if payload.exactLongitude is not None and payload.exactLatitude is not None
        else None
    )
    listing.description = payload.description
    listing.home_description = payload.homeDescription
    listing.advertiser_type = payload.advertiserType
    listing.source = payload.source or None
    listing.expires_at = payload.expiresAt


def apply_room_detail_write(details: ListingRoomDetails, payload: ListingWrite) -> None:
    for api_name, model_name in ROOM_DETAIL_MAPPING.items():
        setattr(details, model_name, getattr(payload, api_name))


def _validate_effective_patch_state(
    listing: Listing, details: ListingRoomDetails | None, changes: dict[str, object]
) -> None:
    def effective(api_name: str, current: object) -> object:
        return changes[api_name] if api_name in changes else current

    room_type = effective("roomType", listing.room_type)
    room_capacity = effective("roomCapacity", listing.room_capacity)
    room_size = effective("roomSizeM2", listing.room_size_m2)
    rental_mode = effective("rentalMode", listing.rental_mode)
    monthly_price = effective("monthlyPrice", listing.monthly_price)
    nightly_price = effective("nightlyPrice", listing.nightly_price)
    available_from = effective("availableFrom", listing.available_from)
    available_until = effective("availableUntil", listing.available_until)

    rental_unit = effective("rentalUnit", details.rental_unit if details else None)
    bed_type = effective("bedType", details.bed_type if details else None)
    bed_count = effective("bedCount", details.bed_count if details else None)
    room_residents = effective(
        "currentRoomResidents", details.current_room_residents if details else None
    )
    home_size = effective("homeSizeM2", details.home_size_m2 if details else None)

    if rental_mode == "long" and monthly_price is None:
        raise HTTPException(422, "monthlyPrice is required for long rentals")
    if rental_mode == "holiday" and nightly_price is None:
        raise HTTPException(422, "nightlyPrice is required for holiday rentals")
    if rental_unit == "bed" and room_type != "Habitación compartida":
        raise HTTPException(422, "rentalUnit=bed is only valid for shared rooms")
    if rental_unit == "bed" and bed_type not in {None, "single"}:
        raise HTTPException(422, "bed-space listings must use single beds")
    if room_residents is not None and room_capacity is not None and room_residents >= room_capacity:
        raise HTTPException(422, "currentRoomResidents must leave at least one available place")
    if bed_count is not None and bed_type is not None and room_capacity is not None:
        sleeping_places = bed_count * (2 if bed_type == "double" else 1)
        if sleeping_places < room_capacity:
            raise HTTPException(422, "bedCount and bedType do not provide enough sleeping places")
    if home_size is not None and room_size is not None and home_size < room_size:
        raise HTTPException(422, "homeSizeM2 cannot be smaller than roomSizeM2")
    if available_from is not None and available_until is not None and available_until < available_from:
        raise HTTPException(422, "availableUntil cannot be before availableFrom")


async def create_listing(payload: ListingWrite, user: User, session: AsyncSession) -> OwnedListingResponse:
    now = datetime.now(UTC)
    initial_status = "published" if get_settings().auto_publish_listings else "pending"
    listing = Listing(
        owner_user_id=user.id,
        approximate_address="",
        title="",
        city="",
        area="",
        rental_mode="long",
        location=point(0, 0),
    )
    apply_write(listing, payload)
    listing.status = initial_status
    listing.published_at = now if initial_status == "published" else None
    session.add(listing)
    await session.flush()
    details = ListingRoomDetails(listing_id=listing.id)
    apply_room_detail_write(details, payload)
    session.add(details)
    session.add(
        ListingStatusHistory(
            listing_id=listing.id,
            from_status="draft",
            to_status=initial_status,
            changed_by=user.id,
        )
    )
    await touch_catalog(session)
    await session.commit()
    row = (await session.execute(owned_query().where(Listing.id == listing.id))).one()
    return owned_response_from(row)


async def update_listing(
    listing_id: UUID,
    payload: ListingPatch,
    user: User,
    session: AsyncSession,
) -> OwnedListingResponse:
    listing = await session.get(Listing, listing_id)
    if not listing or listing.deleted_at is not None:
        raise HTTPException(404, "Listing not found")
    admin = await ensure_owner_or_admin(listing, user, session)
    if not admin and (listing.status == "published" or payload.status in {"pending", "published"}):
        await enforce_publish_access(user, session)
    changes = payload.model_dump(exclude_unset=True)
    if "status" in changes and not admin and changes["status"] not in {"draft", "pending", "hidden", "closed"}:
        raise HTTPException(403, "Only an administrator can publish or reject listings")

    current_details = await session.get(ListingRoomDetails, listing.id)
    _validate_effective_patch_state(listing, current_details, changes)

    mapping = {
        "approximateAddress": "approximate_address",
        "monthlyPrice": "monthly_price",
        "nightlyPrice": "nightly_price",
        "rentalMode": "rental_mode",
        "weeklyPrice": "weekly_price",
        "roomType": "room_type",
        "availableFrom": "available_from",
        "availableUntil": "available_until",
        "minimumStayMonths": "minimum_stay_months",
        "minimumNights": "minimum_nights",
        "depositAmount": "deposit_amount",
        "billsIncluded": "bills_included",
        "roomSizeM2": "room_size_m2",
        "bedroomCount": "bedroom_count",
        "currentResidents": "current_residents",
        "roomCapacity": "room_capacity",
        "tenantRequirement": "tenant_requirement",
        "smokingAllowed": "smoking_allowed",
        "petsAllowed": "pets_allowed",
        "childrenAllowed": "children_allowed",
        "empadronamientoAllowed": "empadronamiento_allowed",
        "homeDescription": "home_description",
        "advertiserType": "advertiser_type",
        "expiresAt": "expires_at",
    }
    detail_changes = {key: changes.pop(key) for key in list(changes) if key in ROOM_DETAIL_MAPPING}
    if detail_changes:
        details = current_details
        if details is None:
            details = ListingRoomDetails(listing_id=listing.id)
            session.add(details)
        for api_name, value in detail_changes.items():
            setattr(details, ROOM_DETAIL_MAPPING[api_name], value)

    previous_status = listing.status
    latitude = changes.pop("latitude", None)
    longitude = changes.pop("longitude", None)
    exact_latitude = changes.pop("exactLatitude", None)
    exact_longitude = changes.pop("exactLongitude", None)
    if latitude is not None and longitude is not None:
        listing.location = point(longitude, latitude)
    if "exactLatitude" in payload.model_fields_set or "exactLongitude" in payload.model_fields_set:
        listing.exact_location = (
            point(exact_longitude, exact_latitude)
            if exact_latitude is not None and exact_longitude is not None
            else None
        )
    for key, value in changes.items():
        setattr(listing, mapping.get(key, key), value)
    if listing.status != previous_status:
        session.add(
            ListingStatusHistory(
                listing_id=listing.id,
                from_status=previous_status,
                to_status=listing.status,
                changed_by=user.id,
            )
        )
        if listing.status == "published" and listing.published_at is None:
            listing.published_at = datetime.now(UTC)
    await touch_catalog(session)
    await session.commit()
    row = (await session.execute(owned_query().where(Listing.id == listing.id))).one()
    return owned_response_from(row)


async def renew_listing(listing_id: UUID, user: User, session: AsyncSession) -> OwnedListingResponse:
    listing = await session.get(Listing, listing_id)
    if not listing or listing.deleted_at is not None:
        raise HTTPException(404, "Listing not found")
    await ensure_owner_or_admin(listing, user, session)
    now = datetime.now(UTC)
    expiry_base = listing.expires_at if listing.expires_at and listing.expires_at > now else now
    listing.expires_at = expiry_base + timedelta(days=30)
    previous_status = listing.status
    listing.status = "published" if get_settings().auto_publish_listings else "pending"
    listing.closed_reason = None
    if listing.status == "published" and listing.published_at is None:
        listing.published_at = now
    if listing.status != previous_status:
        session.add(
            ListingStatusHistory(
                listing_id=listing.id,
                from_status=previous_status,
                to_status=listing.status,
                changed_by=user.id,
            )
        )
    await touch_catalog(session)
    await session.commit()
    row = (await session.execute(owned_query().where(Listing.id == listing.id))).one()
    return owned_response_from(row)


async def delete_listing(listing_id: UUID, user: User, session: AsyncSession) -> None:
    listing = await session.scalar(select(Listing).where(Listing.id == listing_id).with_for_update())
    if not listing or listing.deleted_at is not None:
        raise HTTPException(404, "Listing not found")
    await ensure_owner_or_admin(listing, user, session)
    attached_ids = set(
        (await session.scalars(select(ListingImage.media_asset_id).where(ListingImage.listing_id == listing.id))).all()
    )
    await lock_media_assets(session, attached_ids)
    await session.execute(delete(ListingImage).where(ListingImage.listing_id == listing.id))
    await session.execute(delete(Favorite).where(Favorite.listing_id == listing.id))
    await session.execute(delete(DiscardedListing).where(DiscardedListing.listing_id == listing.id))
    await session.flush()
    await mark_orphaned_media(session, attached_ids)

    previous_status = listing.status
    listing.deleted_at = datetime.now(UTC)
    listing.status = "closed"
    listing.closed_reason = "deleted"
    session.add(
        ListingStatusHistory(
            listing_id=listing.id,
            from_status=previous_status,
            to_status="closed",
            changed_by=user.id,
        )
    )
    await touch_catalog(session)
    await session.commit()


async def replace_listing_images(
    listing_id: UUID,
    payload: ListingImagesRequest,
    user: User,
    session: AsyncSession,
) -> list[ListingImageResponse]:
    listing = await session.scalar(select(Listing).where(Listing.id == listing_id).with_for_update())
    if not listing or listing.deleted_at is not None:
        raise HTTPException(404, "Listing not found")
    admin = await ensure_owner_or_admin(listing, user, session)
    if not admin and listing.status == "published":
        await enforce_publish_access(user, session)
    previous_ids = set(
        (await session.scalars(select(ListingImage.media_asset_id).where(ListingImage.listing_id == listing.id))).all()
    )
    requested_ids = set(payload.assetIds)
    locked_assets = await lock_media_assets(session, previous_ids | requested_ids)
    assets_by_id = {asset.id: asset for asset in locked_assets}
    requested_assets = [assets_by_id.get(asset_id) for asset_id in payload.assetIds]
    if any(
        asset is None
        or asset.deleted_at is not None
        or asset.kind != "listing_image"
        or (not admin and asset.owner_id != user.id)
        for asset in requested_assets
    ):
        raise HTTPException(422, "Every image must be an active listing asset owned by the requester")

    await session.execute(delete(ListingImage).where(ListingImage.listing_id == listing.id))
    for sort_order, asset_id in enumerate(payload.assetIds):
        session.add(
            ListingImage(
                listing_id=listing.id,
                media_asset_id=asset_id,
                sort_order=sort_order,
                is_cover=sort_order == 0,
            )
        )
    await session.flush()
    await mark_orphaned_media(session, previous_ids - requested_ids)
    await session.commit()
    return [
        ListingImageResponse(
            assetId=asset_id,
            url=f"/api/v1/media/{asset_id}",
            sortOrder=order,
            isCover=order == 0,
        )
        for order, asset_id in enumerate(payload.assetIds)
    ]
