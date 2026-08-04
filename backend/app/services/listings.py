from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..models import (
    CatalogState,
    DiscardedListing,
    Favorite,
    Listing,
    ListingImage,
    ListingStatusHistory,
    MediaAsset,
    User,
)
from ..repositories.listings import owned_query, owned_response_from, point
from ..schemas.listings import (
    ListingImageResponse,
    ListingImagesRequest,
    ListingPatch,
    ListingWrite,
    OwnedListingResponse,
)
from .storage_deletions import enqueue_storage_deletions


def ensure_owner_or_admin(listing: Listing, user: User) -> None:
    if listing.owner_user_id != user.id and user.role != "admin":
        raise HTTPException(403, "Forbidden")


async def touch_catalog(session: AsyncSession) -> None:
    state = await session.get(CatalogState, 1)
    if not state:
        state = CatalogState(id=1, version=1)
        session.add(state)
    state.version += 1
    state.updated_at = datetime.now(UTC)


async def mark_orphaned_media(session: AsyncSession, candidate_ids: set[UUID]) -> int:
    if not candidate_ids:
        return 0
    attached = set(
        (
            await session.scalars(
                select(ListingImage.media_asset_id).where(ListingImage.media_asset_id.in_(candidate_ids))
            )
        ).all()
    )
    avatars = {
        value
        for value in (
            await session.scalars(select(User.avatar_asset_id).where(User.avatar_asset_id.in_(candidate_ids)))
        ).all()
        if value is not None
    }
    orphan_ids = candidate_ids - attached - avatars
    if not orphan_ids:
        return 0
    assets = list(
        (
            await session.scalars(
                select(MediaAsset).where(MediaAsset.id.in_(orphan_ids), MediaAsset.deleted_at.is_(None))
            )
        ).all()
    )
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
    ensure_owner_or_admin(listing, user)
    changes = payload.model_dump(exclude_unset=True)
    if (
        "status" in changes
        and user.role != "admin"
        and changes["status"] not in {"draft", "pending", "hidden", "closed"}
    ):
        raise HTTPException(403, "Only an administrator can publish or reject listings")

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
    ensure_owner_or_admin(listing, user)
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
    listing = await session.get(Listing, listing_id)
    if not listing or listing.deleted_at is not None:
        raise HTTPException(404, "Listing not found")
    ensure_owner_or_admin(listing, user)
    attached_ids = set(
        (await session.scalars(select(ListingImage.media_asset_id).where(ListingImage.listing_id == listing.id))).all()
    )
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
    listing = await session.get(Listing, listing_id)
    if not listing or listing.deleted_at is not None:
        raise HTTPException(404, "Listing not found")
    ensure_owner_or_admin(listing, user)
    assets = (
        await session.scalars(
            select(MediaAsset).where(
                MediaAsset.id.in_(payload.assetIds),
                MediaAsset.deleted_at.is_(None),
                MediaAsset.kind == "listing_image",
            )
        )
    ).all()
    if len(assets) != len(payload.assetIds) or any(
        asset.owner_id != user.id for asset in assets if user.role != "admin"
    ):
        raise HTTPException(422, "Every image must be an active listing asset owned by the requester")

    previous_ids = set(
        (await session.scalars(select(ListingImage.media_asset_id).where(ListingImage.listing_id == listing.id))).all()
    )
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
    await mark_orphaned_media(session, previous_ids - set(payload.assetIds))
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
