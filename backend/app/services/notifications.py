from __future__ import annotations

import logging
from datetime import UTC, datetime
from unicodedata import combining, normalize
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Favorite, Listing, Notification, SavedSearch, User
from ..repositories.listings import apply_search_filters, visible_query
from ..schemas.listings import ListingSearchRequest
from ..schemas.notifications import NotificationPage, NotificationResponse
from .mail import enqueue_mail, frontend_link

logger = logging.getLogger(__name__)

# These values mirror the customer-facing defaults. Saved searches persist the
# complete filter object, whereas the live search API sends only active filters.
# Alert matching must therefore neutralize defaults or it will silently narrow
# a saved search compared with the result set the customer actually saved.
_SAVED_SEARCH_DEFAULTS: dict[str, object] = {
    "minPrice": 0,
    "maxPrice": 1200,
    "homeSizeMin": 0,
    "homeSizeMax": 250,
}


def _response(notification: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id,
        type=notification.type,
        entityListingId=notification.entity_listing_id,
        title=notification.title,
        body=notification.body,
        createdAt=notification.created_at,
        readAt=notification.read_at,
    )


async def create_notification(
    session: AsyncSession,
    *,
    recipient: User,
    kind: str,
    title: str,
    body: str,
    entity_listing_id: UUID | None = None,
    idempotency_key: str,
    email_path: str | None = None,
) -> bool:
    """Persist a notification and fan out through the existing outbox once."""
    result = await session.execute(
        insert(Notification)
        .values(
            recipient_user_id=recipient.id,
            type=kind,
            entity_listing_id=entity_listing_id,
            title=title,
            body=body,
            idempotency_key=idempotency_key,
        )
        .on_conflict_do_nothing(index_elements=["recipient_user_id", "idempotency_key"])
        .returning(Notification.id)
    )
    created = result.scalar_one_or_none() is not None
    if created and email_path:
        enqueue_mail(
            session,
            kind=f"notification_{kind}",
            recipient=recipient.email,
            subject=title,
            body=f"{body}\n\n{frontend_link(email_path)}",
        )
    return created


def _changed_filter(filters: dict[object, object], key: str, default: object) -> object | None:
    value = filters.get(key, default)
    return None if value == default else value


def _positive_filter(filters: dict[object, object], key: str) -> object | None:
    value = filters.get(key, 0)
    return None if value == 0 else value


def _saved_yes_no(value: object) -> bool | None:
    if value is None or value == "Cualquiera":
        return None
    if value == "Sí":
        return True
    if value == "No":
        return False
    raise ValueError("invalid saved yes/no filter")


def _saved_true_only(value: object) -> bool | None:
    if value is None or value is False:
        return None
    if value is True:
        return True
    raise ValueError("invalid saved boolean filter")


def _saved_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("invalid saved list filter")
    return value


def _saved_publication_days(value: object) -> int | None:
    if value is None or value == "Cualquiera":
        return None
    if not isinstance(value, str):
        raise ValueError("invalid saved publication filter")
    try:
        return {"24h": 1, "7d": 7, "30d": 30}[value]
    except KeyError as exc:
        raise ValueError("invalid saved publication filter") from exc


def _saved_polygon(value: object) -> list[dict[str, object]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("invalid saved polygon")
    result: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict) or "lat" not in item or "lng" not in item:
            raise ValueError("invalid saved polygon")
        result.append({"latitude": item["lat"], "longitude": item["lng"]})
    return result


def _saved_search_payload(search: SavedSearch) -> ListingSearchRequest | None:
    """Translate persisted customer filters into the canonical search DTO.

    Saved-search rows can outlive several frontend filter schemas. Treat each
    row as untrusted legacy data: any conversion or validation error skips only
    that saved search and must never abort listing publication/import.
    """
    try:
        filters = search.filters if isinstance(search.filters, dict) else {}
        min_stay = filters.get("minStay", "Cualquiera")
        current_residents = filters.get("currentResidents", "Cualquiera")
        room_residents = filters.get("roomResidents", "Cualquiera")
        room_capacity = filters.get("roomCapacity", "Cualquiera")
        amenities = [item for item in _saved_string_list(filters.get("amenities", [])) if item != "Aire acondicionado"]
        payload = {
            "query": search.query or None,
            "rentalMode": search.rental_mode,
            "minPrice": _changed_filter(filters, "minPrice", _SAVED_SEARCH_DEFAULTS["minPrice"]),
            "maxPrice": _changed_filter(filters, "maxPrice", _SAVED_SEARCH_DEFAULTS["maxPrice"]),
            "roomType": None if filters.get("roomType") in {None, "Cualquiera"} else filters.get("roomType"),
            "availableFrom": filters.get("available") or None,
            "availableUntil": filters.get("availableUntil") or None,
            "maxMinimumStayMonths": None if min_stay in {None, "Cualquiera"} else int(min_stay),
            "restrictions": _saved_string_list(filters.get("conditions", [])),
            "tenantRequirement": None if filters.get("tenantRequirement") in {None, "Cualquiera", "any"} else filters.get("tenantRequirement"),
            "bathroom": None if filters.get("bathroom") in {None, "Cualquiera"} else filters.get("bathroom"),
            "kitchen": None if filters.get("kitchen") in {None, "Cualquiera"} else filters.get("kitchen"),
            "furnished": _saved_true_only(filters.get("furnished", False)),
            "billsIncluded": _saved_true_only(filters.get("billsIncluded", False)),
            "deposit": None if filters.get("deposit") in {None, "Cualquiera"} else filters.get("deposit"),
            # Room-size and air-conditioning filters were removed from the
            # customer search surface. Old rows must not keep invisible filters.
            "minRoomSizeM2": None,
            "maxRoomSizeM2": None,
            "minHomeSizeM2": _changed_filter(filters, "homeSizeMin", _SAVED_SEARCH_DEFAULTS["homeSizeMin"]),
            "maxHomeSizeM2": _changed_filter(filters, "homeSizeMax", _SAVED_SEARCH_DEFAULTS["homeSizeMax"]),
            "minBathroomCount": _positive_filter(filters, "bathroomCountMin"),
            "rentalUnit": None if filters.get("rentalUnit") in {None, "Cualquiera"} else filters.get("rentalUnit"),
            "bedType": None if filters.get("bedType") in {None, "Cualquiera"} else filters.get("bedType"),
            "minBedCount": _positive_filter(filters, "bedCountMin"),
            "shower": None if filters.get("shower") in {None, "Cualquiera"} else filters.get("shower"),
            "toilet": None if filters.get("toilet") in {None, "Cualquiera"} else filters.get("toilet"),
            "minCurrentResidents": 5 if current_residents == "5+" else None,
            "currentResidents": None if current_residents in {None, "Cualquiera", "5+"} else int(current_residents),
            "currentRoomResidents": None if room_residents in {None, "Cualquiera"} else int(room_residents),
            "roomCapacity": None if room_capacity in {None, "Cualquiera"} else int(room_capacity),
            "minAvailableSpots": _positive_filter(filters, "availableSpotsMin"),
            "maxMinimumNights": _positive_filter(filters, "minimumNights") if search.rental_mode == "holiday" else None,
            "smokingAllowed": _saved_yes_no(filters.get("smoking", "Cualquiera")),
            "petsAllowed": _saved_yes_no(filters.get("pets", "Cualquiera")),
            "childrenAllowed": _saved_yes_no(filters.get("children", "Cualquiera")),
            "couplesAllowed": _saved_yes_no(filters.get("couplesAllowed", "Cualquiera")),
            "householdGender": None if filters.get("householdGender") in {None, "Cualquiera"} else filters.get("householdGender"),
            "householdHasChildren": _saved_yes_no(filters.get("householdHasChildren", "Cualquiera")),
            "heatingType": None if filters.get("heatingType") in {None, "Cualquiera"} else filters.get("heatingType"),
            "accessible": _saved_yes_no(filters.get("accessible", "Cualquiera")),
            "floor": None if filters.get("floor") in {None, "Cualquiera"} else filters.get("floor"),
            "acceptedTenantTypes": _saved_string_list(filters.get("acceptedTenantTypes", [])),
            "empadronamientoAllowed": _saved_yes_no(filters.get("empadronamiento", "Cualquiera")),
            "publishedWithinDays": _saved_publication_days(filters.get("publicationDate", "Cualquiera")),
            "advertiserType": None if filters.get("advertiserType") in {None, "Cualquiera"} else filters.get("advertiserType"),
            "amenities": amenities,
            "polygon": _saved_polygon(getattr(search, "polygon", [])),
            "limit": 1,
        }
        return ListingSearchRequest.model_validate(payload)
    except (KeyError, TypeError, ValueError):
        logger.warning(
            "saved_search_alert_filters_invalid",
            extra={"saved_search_id": str(getattr(search, "id", "unknown"))},
        )
        return None


def _zone_slug(value: object) -> str:
    """Match stable municipality ids to listing cities without guessing detail zones."""
    plain = "".join(char for char in normalize("NFKD", str(value).casefold()) if not combining(char))
    return "-".join("".join(char if char.isalnum() else " " for char in plain).split())


def _listing_matches_saved_areas(listing: Listing, filters: dict[object, object]) -> bool:
    areas = filters.get("areas")
    if areas is None or areas == []:
        return True
    if not isinstance(areas, list):
        return False
    city = _zone_slug(listing.city)
    for area in areas:
        if not isinstance(area, str):
            return False
        zone = area.strip()
        if zone.startswith("municipality:"):
            if _zone_slug(zone.removeprefix("municipality:")) == city:
                return True
        elif ":" not in zone and _zone_slug(zone) == city:
            return True
    # District/neighbourhood geometry belongs to the client hierarchy. Until it
    # is represented server-side, do not broaden an alert to the whole city.
    return False


async def notify_saved_search_matches(session: AsyncSession, listing: Listing) -> None:
    """Create one durable alert per saved-search/listing pair after publication."""
    rows = (await session.execute(
        select(SavedSearch, User)
        .join(User, User.id == SavedSearch.user_id)
        .where(SavedSearch.alerts_enabled.is_(True), User.deleted_at.is_(None), User.blocked.is_(False))
    )).all()
    for search, recipient in rows:
        if recipient.id == listing.owner_user_id:
            continue
        request = _saved_search_payload(search)
        if request is None:
            continue
        filters = search.filters if isinstance(search.filters, dict) else {}
        if not _listing_matches_saved_areas(listing, filters):
            continue
        matched = await session.scalar(
            apply_search_filters(visible_query(), request)
            .where(Listing.id == listing.id)
            .with_only_columns(Listing.id)
            .limit(1)
        )
        if matched:
            await create_notification(
                session,
                recipient=recipient,
                kind="saved_search_match",
                title="Nueva habitación para tu búsqueda guardada",
                body=f"{listing.title} coincide con una de tus búsquedas guardadas.",
                entity_listing_id=listing.id,
                idempotency_key=f"saved-search:{search.id}:{listing.id}",
                email_path=f"/habitacion/{listing.id}",
            )


async def notify_favorited_listing_unavailable(
    session: AsyncSession, listing: Listing, *, event_key: str
) -> None:
    recipients = (await session.scalars(
        select(User)
        .join(Favorite, Favorite.user_id == User.id)
        .where(
            Favorite.listing_id == listing.id,
            User.deleted_at.is_(None),
            User.blocked.is_(False),
        )
    )).all()
    for recipient in recipients:
        await create_notification(
            session,
            recipient=recipient,
            kind="favorite_unavailable",
            title="Un favorito ya no está disponible",
            body=f"{listing.title} ya no aparece en las búsquedas públicas.",
            entity_listing_id=listing.id,
            idempotency_key=f"favorite-unavailable:{listing.id}:{event_key}",
            email_path="/favoritos",
        )


async def list_notifications(user: User, session: AsyncSession, *, limit: int, offset: int) -> NotificationPage:
    unread = await session.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.recipient_user_id == user.id,
            Notification.read_at.is_(None),
        )
    )
    items = list((await session.scalars(
        select(Notification)
        .where(Notification.recipient_user_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
        .offset(offset)
    )).all())
    return NotificationPage(items=[_response(item) for item in items], unreadCount=int(unread or 0))


async def mark_notification_read(notification_id: UUID, user: User, session: AsyncSession) -> None:
    result = await session.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.recipient_user_id == user.id)
        .values(read_at=datetime.now(UTC))
        .returning(Notification.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(404, "Notification not found")
    await session.commit()


async def mark_all_notifications_read(user: User, session: AsyncSession) -> None:
    await session.execute(
        update(Notification)
        .where(Notification.recipient_user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    await session.commit()
