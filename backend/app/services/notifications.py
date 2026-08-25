from __future__ import annotations

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


def _saved_search_payload(search: SavedSearch) -> ListingSearchRequest | None:
    """Translate the customer filter shape stored with a saved search once.

    Saved-search state predates the API search DTO, so alert matching must use
    the same canonical SQL predicates rather than a weaker client-side subset.
    Invalid legacy data is ignored safely instead of broadening an alert.
    """
    filters = search.filters if isinstance(search.filters, dict) else {}
    yes_no = lambda value: None if value == "Cualquiera" else value == "Sí"
    publication_value = filters.get("publicationDate")
    publication = {"24h": 1, "7d": 7, "30d": 30}.get(publication_value) if isinstance(publication_value, str) else None
    payload = {
        "query": search.query or None,
        "rentalMode": search.rental_mode,
        "minPrice": filters.get("minPrice"), "maxPrice": filters.get("maxPrice"),
        "roomType": None if filters.get("roomType") == "Cualquiera" else filters.get("roomType"),
        "availableFrom": filters.get("available") or None,
        "availableUntil": filters.get("availableUntil") or None,
        "maxMinimumStayMonths": None if filters.get("minStay") in {None, "Cualquiera"} else int(filters["minStay"]),
        "restrictions": filters.get("conditions", []),
        "tenantRequirement": None if filters.get("tenantRequirement") in {None, "Cualquiera", "any"} else filters.get("tenantRequirement"),
        "bathroom": None if filters.get("bathroom") in {None, "Cualquiera"} else filters.get("bathroom"),
        "kitchen": None if filters.get("kitchen") in {None, "Cualquiera"} else filters.get("kitchen"),
        "furnished": True if filters.get("furnished") else None,
        "billsIncluded": True if filters.get("billsIncluded") else None,
        "deposit": None if filters.get("deposit") in {None, "Cualquiera"} else filters.get("deposit"),
        "minRoomSizeM2": filters.get("roomSizeMin"), "maxRoomSizeM2": filters.get("roomSizeMax"),
        "minHomeSizeM2": filters.get("homeSizeMin"), "maxHomeSizeM2": filters.get("homeSizeMax"),
        "minBathroomCount": filters.get("bathroomCountMin") or None,
        "rentalUnit": None if filters.get("rentalUnit") in {None, "Cualquiera"} else filters.get("rentalUnit"),
        "bedType": None if filters.get("bedType") in {None, "Cualquiera"} else filters.get("bedType"),
        "minBedCount": filters.get("bedCountMin") or None,
        "shower": None if filters.get("shower") in {None, "Cualquiera"} else filters.get("shower"),
        "toilet": None if filters.get("toilet") in {None, "Cualquiera"} else filters.get("toilet"),
        "minCurrentResidents": 5 if filters.get("currentResidents") == "5+" else None,
        "currentResidents": None if filters.get("currentResidents") in {None, "Cualquiera", "5+"} else int(filters["currentResidents"]),
        "currentRoomResidents": None if filters.get("roomResidents") in {None, "Cualquiera"} else int(filters["roomResidents"]),
        "roomCapacity": None if filters.get("roomCapacity") in {None, "Cualquiera"} else int(filters["roomCapacity"]),
        "minAvailableSpots": filters.get("availableSpotsMin") or None,
        "maxMinimumNights": (filters.get("minimumNights") or None) if search.rental_mode == "holiday" else None,
        "smokingAllowed": yes_no(filters.get("smoking", "Cualquiera")),
        "petsAllowed": yes_no(filters.get("pets", "Cualquiera")),
        "childrenAllowed": yes_no(filters.get("children", "Cualquiera")),
        "couplesAllowed": yes_no(filters.get("couplesAllowed", "Cualquiera")),
        "householdGender": None if filters.get("householdGender") in {None, "Cualquiera"} else filters.get("householdGender"),
        "householdHasChildren": yes_no(filters.get("householdHasChildren", "Cualquiera")),
        "heatingType": None if filters.get("heatingType") in {None, "Cualquiera"} else filters.get("heatingType"),
        "accessible": yes_no(filters.get("accessible", "Cualquiera")),
        "floor": None if filters.get("floor") in {None, "Cualquiera"} else filters.get("floor"),
        "acceptedTenantTypes": filters.get("acceptedTenantTypes", []),
        "empadronamientoAllowed": yes_no(filters.get("empadronamiento", "Cualquiera")),
        "publishedWithinDays": publication,
        "advertiserType": None if filters.get("advertiserType") in {None, "Cualquiera"} else filters.get("advertiserType"),
        "amenities": filters.get("amenities", []),
        "polygon": [{"latitude": item["lat"], "longitude": item["lng"]} for item in search.polygon if isinstance(item, dict) and "lat" in item and "lng" in item],
        "limit": 1,
    }
    try:
        return ListingSearchRequest.model_validate(payload)
    except (TypeError, ValueError):
        return None


def _zone_slug(value: object) -> str:
    """Match stable municipality ids to listing cities without guessing detail zones."""
    plain = "".join(char for char in normalize("NFKD", str(value).casefold()) if not combining(char))
    return "-".join("".join(char if char.isalnum() else " " for char in plain).split())


def _listing_matches_saved_areas(listing: Listing, filters: dict[object, object]) -> bool:
    areas = filters.get("areas")
    if not isinstance(areas, list) or not areas:
        return True
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
        select(User).join(Favorite, Favorite.user_id == User.id).where(Favorite.listing_id == listing.id)
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
