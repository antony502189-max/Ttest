from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
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
from .notifications import create_notification, notify_favorited_listing_unavailable, notify_saved_search_matches
from .storage_deletions import enqueue_storage_deletions
from .users import apply_profile_fields

# This is deliberately independent from the product role and AdminAccess
# allow-list. A role carried in a token or client state must never turn an
# ordinary lifecycle action into a destructive purge.
HARD_DELETE_EMAILS = frozenset({"antony502189@gmail.com", "tf.shuler@gmail.com"})

# Owners can only move through the lifecycle exposed by Mis anuncios.  Admin
# moderation has its own stricter transition table and endpoint; accepting an
# arbitrary enum value here would let either actor bypass those rules with a
# direct PATCH request.
OWNER_STATUS_TRANSITIONS = {
    "draft": {"pending", "published"},
    "pending": {"hidden", "closed"},
    "published": {"hidden", "closed"},
    "hidden": {"pending", "published", "closed"},
    "closed": set(),
    "rejected": {"pending", "published", "closed"},
}


def canonical_email(value: str) -> str:
    return value.strip().lower()


def require_hard_delete_authorization(user: User) -> None:
    # Email addresses are not proof of account ownership until the verification
    # flow (or an authoritative Google identity) has set this server-side flag.
    # In particular, a newly registered password account must not be able to
    # claim an allowlisted address and purge another user's listing.
    if canonical_email(user.email) not in HARD_DELETE_EMAILS or not user.email_verified:
        raise HTTPException(403, "Hard deletion is restricted")


def resolve_owner_status_transition(current: str, requested: str, *, auto_publish: bool) -> str:
    target = "published" if requested == "published" and auto_publish else (
        "pending" if requested == "published" else requested
    )
    if target != current and target not in OWNER_STATUS_TRANSITIONS[current]:
        raise HTTPException(409, "Listing status transition is not permitted")
    return target

ROOM_DETAIL_MAPPING = {
    "homeSizeM2": "home_size_m2",
    "bathroomCount": "bathroom_count",
    "rentalUnit": "rental_unit",
    "bedType": "bed_type_v2",
    "roomCapacity": "room_capacity_v2",
    "bedCount": "bed_count",
    "currentRoomResidents": "current_room_residents",
    "toilet": "toilet",
    "householdGender": "household_gender",
    "householdHasChildren": "household_has_children",
    "heatingType": "heating_type",
    "accessible": "accessible",
    "floor": "floor",
    "couplesAllowed": "couples_allowed",
    "acceptedTenantTypes": "accepted_tenant_types",
}


def _legacy_bed_type(value: str | None) -> str | None:
    """Mirror new values into the old constrained column during the expand phase."""
    return "single" if value == "bunk" else value


def _legacy_room_capacity(value: int | None) -> int | None:
    """Mirror the expanded 1..10 value into the old 1..2 column."""
    return min(value, 2) if value is not None else None


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


async def _lock_active_user(user_id: UUID, session: AsyncSession) -> User:
    """Lock and refresh a live user row before a stateful listing mutation.

    Account deletion locks the user row before touching owned listings. Taking
    the same row lock here prevents a request-scoped, preloaded User object from
    creating or mutating durable listing state after deletion has committed.
    ``populate_existing`` makes the post-wait deletion check authoritative even
    when SQLAlchemy already has the user in its identity map.
    """
    user = await session.scalar(
        select(User)
        .where(User.id == user_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )
    if not user or user.deleted_at is not None:
        raise HTTPException(404, "User not found")
    return user


async def _lock_mutable_listing(listing_id: UUID, session: AsyncSession) -> tuple[Listing, User]:
    """Lock a listing with the global account-deletion lock order: User -> Listing.

    The initial owner-id read is intentionally lock-free because ownership is
    immutable. We then lock and refresh the owner before locking/revalidating
    the listing itself. This matches admin moderation and account deletion, so
    owner/admin mutations cannot validate stale lifecycle state or introduce a
    User/Listing lock-order inversion.
    """
    owner_id = await session.scalar(
        select(Listing.owner_user_id).where(
            Listing.id == listing_id,
            Listing.deleted_at.is_(None),
        )
    )
    if owner_id is None:
        raise HTTPException(404, "Listing not found")

    owner = await _lock_active_user(owner_id, session)
    listing = await session.scalar(
        select(Listing)
        .where(
            Listing.id == listing_id,
            Listing.owner_user_id == owner.id,
            Listing.deleted_at.is_(None),
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )
    if not listing:
        raise HTTPException(404, "Listing not found")
    return listing, owner


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
    listing.bills_text = payload.billsText
    listing.bathroom = payload.bathroom
    listing.kitchen = payload.kitchen
    listing.furnished = payload.furnished
    listing.room_size_m2 = payload.roomSizeM2
    listing.bedroom_count = payload.bedroomCount
    listing.current_residents = payload.currentResidents
    listing.room_capacity = _legacy_room_capacity(payload.roomCapacity)
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
    listing.expires_at = payload.expiresAt


def apply_room_detail_write(details: ListingRoomDetails, payload: ListingWrite) -> None:
    for api_name, model_name in ROOM_DETAIL_MAPPING.items():
        setattr(details, model_name, getattr(payload, api_name))
    details.bed_type = _legacy_bed_type(payload.bedType)


def _validate_effective_patch_state(
    listing: Listing, details: ListingRoomDetails | None, changes: dict[str, object]
) -> None:
    def effective[T](api_name: str, current: T) -> T:
        return cast(T, changes.get(api_name, current))

    room_type = effective("roomType", listing.room_type)
    stored_capacity = (
        details.room_capacity_v2
        if details is not None and getattr(details, "room_capacity_v2", None) is not None
        else listing.room_capacity
    )
    room_capacity = effective("roomCapacity", stored_capacity)
    room_size = effective("roomSizeM2", listing.room_size_m2)
    rental_mode = effective("rentalMode", listing.rental_mode)
    monthly_price = effective("monthlyPrice", listing.monthly_price)
    nightly_price = effective("nightlyPrice", listing.nightly_price)
    available_from = effective("availableFrom", listing.available_from)
    available_until = effective("availableUntil", listing.available_until)

    rental_unit = effective("rentalUnit", details.rental_unit if details else None)
    bed_type = effective("bedType", (getattr(details, "bed_type_v2", None) or details.bed_type) if details else None)
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
    if rental_unit == "bed" and bed_type not in {None, "single", "bunk"}:
        raise HTTPException(422, "bed-space listings must use single or bunk beds")
    if room_residents is not None and room_capacity is not None and room_residents >= room_capacity:
        raise HTTPException(422, "currentRoomResidents must leave at least one available place")
    if bed_count is not None and bed_type is not None and room_capacity is not None:
        sleeping_places = bed_count * (2 if bed_type in {"double", "bunk"} else 1)
        if sleeping_places < room_capacity:
            raise HTTPException(422, "bedCount and bedType do not provide enough sleeping places")
    if home_size is not None and room_size is not None and home_size < room_size:
        raise HTTPException(422, "homeSizeM2 cannot be smaller than roomSizeM2")
    if available_from is not None and available_until is not None and available_until < available_from:
        raise HTTPException(422, "availableUntil cannot be before availableFrom")


def apply_publication_contact(payload: ListingWrite, user: User) -> None:
    fields = {
        api_name: value
        for api_name, value in {
            "name": payload.contactName,
            "phone": payload.contactPhone,
            "whatsapp": payload.contactWhatsapp,
            "showPhone": payload.showPhone,
            "showWhatsApp": payload.showWhatsApp,
        }.items()
        if value is not None
    }
    apply_profile_fields(user, fields)


async def create_listing(
    payload: ListingWrite,
    user: User,
    session: AsyncSession,
    *,
    listing_id: UUID | None = None,
) -> OwnedListingResponse:
    # The request dependency may have loaded this account before a concurrent
    # deletion started. Serialize with delete_account() and refresh the row
    # before changing profile/listing state so a deleted account cannot publish
    # after the deletion transaction commits.
    user = await _lock_active_user(user.id, session)
    now = datetime.now(UTC)
    initial_status = "published" if get_settings().auto_publish_listings else "pending"
    apply_publication_contact(payload, user)
    listing = Listing(
        **({"id": listing_id} if listing_id is not None else {}),
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
    history = ListingStatusHistory(
        listing_id=listing.id,
        from_status="draft",
        to_status=initial_status,
        changed_by=user.id,
    )
    session.add(history)
    await session.flush()
    await create_notification(
        session,
        recipient=user,
        kind="listing_published" if initial_status == "published" else "listing_submitted",
        title="Tu anuncio está publicado" if initial_status == "published" else "Tu anuncio se ha enviado",
        body=(
            "Tu anuncio ya es visible en 112233.es."
            if initial_status == "published"
            else "Revisaremos tu anuncio antes de publicarlo."
        ),
        entity_listing_id=listing.id,
        idempotency_key=f"listing-status:{history.id}",
        email_path=f"/habitacion/{listing.id}",
    )
    if initial_status == "published":
        await notify_saved_search_matches(session, listing)
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
    listing, owner = await _lock_mutable_listing(listing_id, session)
    admin = await ensure_owner_or_admin(listing, user, session)
    if admin and payload.status is not None and payload.status != listing.status:
        raise HTTPException(403, "Administrators must use the moderation status endpoint")
    if not admin and (listing.status == "published" or payload.status in {"pending", "published"}):
        await enforce_publish_access(user, session)
    changes = payload.model_dump(exclude_unset=True)
    if "status" in changes and not admin:
        # "Show" is a publication intent. Production always returns the
        # listing to moderation; local auto-publish environments may expose it
        # immediately.
        changes["status"] = resolve_owner_status_transition(
            listing.status,
            cast(str, changes["status"]),
            auto_publish=get_settings().auto_publish_listings,
        )

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
        "billsText": "bills_text",
        "roomSizeM2": "room_size_m2",
        "bedroomCount": "bedroom_count",
        "currentResidents": "current_residents",
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
            if api_name == "bedType":
                details.bed_type = _legacy_bed_type(value if isinstance(value, str) else None)
            elif api_name == "roomCapacity":
                listing.room_capacity = _legacy_room_capacity(value if isinstance(value, int) else None)

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
        history = ListingStatusHistory(
            listing_id=listing.id,
            from_status=previous_status,
            to_status=listing.status,
            changed_by=user.id,
        )
        session.add(history)
        if listing.status == "published" and listing.published_at is None:
            listing.published_at = datetime.now(UTC)
        await session.flush()
        notification_copy = {
            "published": ("listing_published", "Tu anuncio está publicado", "Tu anuncio ya es visible en 112233.es."),
            "rejected": ("listing_rejected", "Tu anuncio necesita cambios", "Revisa el estado de tu anuncio antes de volver a publicarlo."),
            "hidden": ("listing_hidden", "Tu anuncio está oculto", "Tu anuncio ya no aparece en las búsquedas públicas."),
            "closed": ("listing_closed", "Tu anuncio está cerrado", "Tu anuncio ya no aparece en las búsquedas públicas."),
        }.get(listing.status)
        if notification_copy:
            kind, title, body = notification_copy
            await create_notification(
                session,
                recipient=owner,
                kind=kind,
                title=title,
                body=body,
                entity_listing_id=listing.id,
                idempotency_key=f"listing-status:{history.id}",
                email_path=f"/habitacion/{listing.id}",
            )
        if listing.status == "published":
            await notify_saved_search_matches(session, listing)
        elif listing.status in {"hidden", "closed", "rejected"}:
            await notify_favorited_listing_unavailable(session, listing, event_key=str(history.id))
    await touch_catalog(session)
    await session.commit()
    row = (await session.execute(owned_query().where(Listing.id == listing.id))).one()
    return owned_response_from(row)


async def renew_listing(listing_id: UUID, user: User, session: AsyncSession) -> OwnedListingResponse:
    listing, owner = await _lock_mutable_listing(listing_id, session)
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
        history = ListingStatusHistory(
            listing_id=listing.id,
            from_status=previous_status,
            to_status=listing.status,
            changed_by=user.id,
        )
        session.add(history)
        await session.flush()
        await create_notification(
            session,
            recipient=owner,
            kind="listing_republished" if listing.status == "published" else "listing_submitted",
            title="Tu anuncio se ha republicado" if listing.status == "published" else "Tu anuncio se ha enviado",
            body=(
                "Tu anuncio vuelve a estar visible en 112233.es."
                if listing.status == "published"
                else "Revisaremos tu anuncio antes de publicarlo."
            ),
            entity_listing_id=listing.id,
            idempotency_key=f"listing-status:{history.id}",
            email_path=f"/habitacion/{listing.id}",
        )
    if listing.status == "published":
        await notify_saved_search_matches(session, listing)
    await touch_catalog(session)
    await session.commit()
    row = (await session.execute(owned_query().where(Listing.id == listing.id))).one()
    return owned_response_from(row)


async def delete_listing(listing_id: UUID, user: User, session: AsyncSession) -> None:
    # `DELETE` also removes media relations and favorites, therefore this is a
    # destructive operation even though the listing row retains a tombstone.
    # Check the canonical, server-loaded account email before inspecting the
    # target so neither ownership nor a forged client role is a bypass.
    require_hard_delete_authorization(user)
    listing, _owner = await _lock_mutable_listing(listing_id, session)
    await ensure_owner_or_admin(listing, user, session)
    attached_ids = set(
        (await session.scalars(select(ListingImage.media_asset_id).where(ListingImage.listing_id == listing.id))).all()
    )
    await lock_media_assets(session, attached_ids)
    await session.execute(delete(ListingImage).where(ListingImage.listing_id == listing.id))
    await session.execute(delete(DiscardedListing).where(DiscardedListing.listing_id == listing.id))
    await session.flush()
    await mark_orphaned_media(session, attached_ids)

    previous_status = listing.status
    listing.deleted_at = datetime.now(UTC)
    listing.status = "closed"
    listing.closed_reason = "deleted"
    history = ListingStatusHistory(
        listing_id=listing.id,
        from_status=previous_status,
        to_status="closed",
        changed_by=user.id,
    )
    session.add(history)
    await session.flush()
    await notify_favorited_listing_unavailable(session, listing, event_key=str(history.id))
    await session.execute(delete(Favorite).where(Favorite.listing_id == listing.id))
    await touch_catalog(session)
    await session.commit()


async def replace_listing_images(
    listing_id: UUID,
    payload: ListingImagesRequest,
    user: User,
    session: AsyncSession,
) -> list[ListingImageResponse]:
    listing, _owner = await _lock_mutable_listing(listing_id, session)
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
        raise HTTPException(
            422,
            detail={
                "code": "LISTING_IMAGE_INVALID",
                "message": "Every image must be an active listing asset owned by the requester.",
                "fieldErrors": {"assetIds": "Remove unavailable images and upload them again."},
            },
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
