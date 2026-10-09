from __future__ import annotations

import base64
import binascii
import json
import math
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from hmac import new as hmac_new
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from geoalchemy2 import Geography, Geometry
from geoalchemy2.functions import (
    ST_X,
    ST_Y,
    ST_DWithin,
    ST_GeomFromText,
    ST_Intersects,
    ST_MakeEnvelope,
    ST_MakePoint,
    ST_SetSRID,
)
from sqlalchemy import Float, Select, and_, case, cast, func, or_, select, update
from sqlalchemy.dialects.postgresql import aggregate_order_by, insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..core.media_limits import MAX_LISTING_PHOTOS
from ..models import Listing, ListingImage, ListingView, MediaAsset, User
from ..models.moderation import ListingPromotion, ListingRestriction, UserRestriction
from ..models.room_details import ListingRoomDetails
from ..schemas.listings import (
    ClusterMarker,
    ListingCardResponse,
    ListingCardSearchRequest,
    ListingCardSearchResponse,
    ListingMapRequest,
    ListingMapResponse,
    ListingMarker,
    ListingOwnerResponse,
    ListingResponse,
    ListingSearchRequest,
    ListingSearchResponse,
    OwnedListingResponse,
)
from ..services.rental_policy import monthly_rent_expression, monthly_rent_total, public_eligibility_clause


def point(longitude: float, latitude: float):
    return ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)


def primary_price_expression():
    return monthly_rent_expression()


def bedroom_count_expression():
    inferred = case((Listing.room_type == "Estudio", 1), else_=Listing.current_residents + 1)
    return func.coalesce(Listing.bedroom_count, inferred)


def image_asset_ids_subquery():
    return (
        select(func.array_agg(aggregate_order_by(MediaAsset.id, ListingImage.is_cover.desc(), ListingImage.sort_order)))
        .join(ListingImage, ListingImage.media_asset_id == MediaAsset.id)
        .where(ListingImage.listing_id == Listing.id, MediaAsset.deleted_at.is_(None))
        .correlate(Listing)
        .scalar_subquery()
    )


def cover_asset_id_subquery():
    return (
        select(MediaAsset.id)
        .join(ListingImage, ListingImage.media_asset_id == MediaAsset.id)
        .where(ListingImage.listing_id == Listing.id, MediaAsset.deleted_at.is_(None))
        .order_by(ListingImage.is_cover.desc(), ListingImage.sort_order)
        .limit(1)
        .correlate(Listing)
        .scalar_subquery()
    )


def active_promotion_expression():
    return (
        select(ListingPromotion.listing_id)
        .where(
            ListingPromotion.listing_id == Listing.id,
            ListingPromotion.starts_at <= func.now(),
            or_(ListingPromotion.ends_at.is_(None), ListingPromotion.ends_at > func.now()),
        )
        .correlate(Listing)
        .exists()
    )


def promotion_boosted_at_expression():
    return (
        select(ListingPromotion.boosted_at)
        .where(
            ListingPromotion.listing_id == Listing.id,
            ListingPromotion.starts_at <= func.now(),
            or_(ListingPromotion.ends_at.is_(None), ListingPromotion.ends_at > func.now()),
        )
        .correlate(Listing)
        .scalar_subquery()
    )


def promotion_ends_at_expression():
    return (
        select(ListingPromotion.ends_at)
        .where(
            ListingPromotion.listing_id == Listing.id,
            ListingPromotion.starts_at <= func.now(),
            or_(ListingPromotion.ends_at.is_(None), ListingPromotion.ends_at > func.now()),
        )
        .correlate(Listing)
        .scalar_subquery()
    )


def response_from(row: Any) -> ListingResponse:
    listing, longitude, latitude, owner, asset_ids, room_details, *promotion = row
    boosted_at = promotion[0] if promotion else None
    price = monthly_rent_total(listing) if listing.rental_mode == "long" else listing.nightly_price
    image_urls = [f"/api/v1/media/{asset_id}" for asset_id in (asset_ids or [])[:MAX_LISTING_PHOTOS]]
    if not image_urls:
        image_urls = list(listing.external_image_urls or [])[:MAX_LISTING_PHOTOS]
    current_room_residents = room_details.current_room_residents if room_details else None
    room_capacity = (
        room_details.room_capacity_v2
        if room_details and getattr(room_details, "room_capacity_v2", None) is not None
        else listing.room_capacity
    )
    available_spots = (
        max(0, room_capacity - current_room_residents)
        if room_capacity is not None and current_room_residents is not None
        else None
    )
    return ListingResponse(
        id=str(listing.id),
        ownerUserId=str(listing.owner_user_id),
        owner=ListingOwnerResponse(
            name=owner.name,
            initials=owner.initials or "".join(part[:1].upper() for part in owner.name.split()[:2]),
            since=owner.created_at,
            response="Consulta disponibilidad",
            verified=owner.email_verified,
        ),
        contactPhone=listing.external_contact_phone
        if listing.is_external
        else (owner.phone if owner.show_phone else None),
        contactWhatsapp=listing.external_contact_whatsapp
        if listing.is_external
        else (owner.whatsapp if owner.show_whatsapp else None),
        contactEmail=listing.external_contact_email if listing.is_external else None,
        showPhone=bool(listing.external_contact_phone) if listing.is_external else owner.show_phone,
        showWhatsApp=bool(listing.external_contact_whatsapp) if listing.is_external else owner.show_whatsapp,
        coverImageUrl=image_urls[0] if image_urls else None,
        imageUrls=image_urls,
        videoUrl=(
            f"/api/v1/media/{listing.video_asset_id}"
            if getattr(listing, "video_asset_id", None)
            else None
        ),
        title=listing.title,
        city=listing.city,
        area=listing.area,
        approximateAddress=listing.approximate_address,
        rentalMode=listing.rental_mode,
        monthlyPrice=listing.monthly_price,
        nightlyPrice=listing.nightly_price,
        weeklyPrice=listing.weekly_price,
        price=price,
        cadence="mes" if listing.rental_mode == "long" else "noche",
        roomType=listing.room_type,
        availableFrom=listing.available_from,
        availableUntil=listing.available_until,
        minimumStayMonths=listing.minimum_stay_months,
        minimumNights=listing.minimum_nights,
        depositAmount=listing.deposit_amount,
        depositText=listing.deposit_text,
        billsIncluded=listing.bills_included,
        billsText=listing.bills_text,
        bathroom=listing.bathroom,
        kitchen=listing.kitchen,
        furnished=listing.furnished,
        roomSizeM2=listing.room_size_m2,
        bedroomCount=listing.bedroom_count,
        currentResidents=listing.current_residents,
        roomCapacity=room_capacity,
        shower=listing.shower,
        tenantRequirement=listing.tenant_requirement,
        smokingAllowed=listing.smoking_allowed,
        petsAllowed=listing.pets_allowed,
        childrenAllowed=listing.children_allowed,
        empadronamientoAllowed=listing.empadronamiento_allowed,
        homeSizeM2=room_details.home_size_m2 if room_details else None,
        bathroomCount=room_details.bathroom_count if room_details else None,
        rentalUnit=room_details.rental_unit if room_details else None,
        bedType=(getattr(room_details, "bed_type_v2", None) or room_details.bed_type) if room_details else None,
        bedCount=room_details.bed_count if room_details else None,
        currentRoomResidents=current_room_residents,
        availableSpots=available_spots,
        toilet=room_details.toilet if room_details else None,
        householdGender=room_details.household_gender if room_details else None,
        householdHasChildren=room_details.household_has_children if room_details else None,
        heatingType=room_details.heating_type if room_details else None,
        accessible=room_details.accessible if room_details else None,
        floor=getattr(room_details, "floor", None) if room_details else None,
        couplesAllowed=room_details.couples_allowed if room_details else None,
        acceptedTenantTypes=room_details.accepted_tenant_types if room_details else [],
        restrictions=listing.restrictions,
        amenities=listing.amenities,
        status=listing.status,
        longitude=longitude,
        latitude=latitude,
        description=listing.description,
        homeDescription=listing.home_description,
        advertiserType=listing.advertiser_type,
        advertiserName=listing.advertiser_name,
        source=listing.source,
        isExternal=listing.is_external,
        primarySource=listing.primary_source,
        sourceUrl=listing.primary_source_url,
        sourcePriceText=listing.source_price_text,
        priceCurrency=listing.source_price_currency,
        pricePeriod=listing.source_price_period,
        priceIsFrom=listing.source_price_is_from,
        publishedAt=listing.published_at,
        expiresAt=listing.expires_at,
        views=listing.views,
        closedReason=listing.closed_reason,
        createdAt=listing.created_at,
        updatedAt=listing.updated_at,
        promoted=boosted_at is not None,
    )


def owned_response_from(row: Any) -> OwnedListingResponse:
    listing, longitude, latitude, owner, asset_ids, room_details, exact_longitude, exact_latitude, *promotion = row
    boosted_at = promotion[0] if promotion else None
    ends_at = promotion[1] if len(promotion) > 1 else None
    public = response_from((listing, longitude, latitude, owner, asset_ids, room_details, boosted_at)).model_dump()
    return OwnedListingResponse(
        **public,
        street=listing.street,
        postcode=listing.postcode,
        exactLatitude=exact_latitude,
        exactLongitude=exact_longitude,
        promotionEndsAt=ends_at,
    )


def visible_query() -> Select:
    active_user_restriction = (
        select(UserRestriction.id)
        .where(
            UserRestriction.user_id == User.id,
            UserRestriction.revoked_at.is_(None),
            UserRestriction.starts_at <= func.now(),
            or_(UserRestriction.ends_at.is_(None), UserRestriction.ends_at > func.now()),
        )
        .correlate(User)
        .exists()
    )
    active_listing_restriction = (
        select(ListingRestriction.id)
        .where(
            ListingRestriction.listing_id == Listing.id,
            ListingRestriction.revoked_at.is_(None),
            ListingRestriction.starts_at <= func.now(),
            or_(ListingRestriction.ends_at.is_(None), ListingRestriction.ends_at > func.now()),
        )
        .correlate(Listing)
        .exists()
    )
    return (
        select(
            Listing,
            ST_X(cast(Listing.location, Geometry("POINT", srid=4326))),
            ST_Y(cast(Listing.location, Geometry("POINT", srid=4326))),
            User,
            image_asset_ids_subquery(),
            ListingRoomDetails,
            promotion_boosted_at_expression(),
        )
        .join(User, User.id == Listing.owner_user_id)
        .outerjoin(ListingRoomDetails, ListingRoomDetails.listing_id == Listing.id)
        .where(
            Listing.status == "published",
            public_eligibility_clause(),
            Listing.deleted_at.is_(None),
            User.deleted_at.is_(None),
            User.blocked.is_(False),
            ~active_user_restriction,
            ~active_listing_restriction,
        )
    )


def owned_query() -> Select:
    return (
        select(
            Listing,
            ST_X(cast(Listing.location, Geometry("POINT", srid=4326))),
            ST_Y(cast(Listing.location, Geometry("POINT", srid=4326))),
            User,
            image_asset_ids_subquery(),
            ListingRoomDetails,
            ST_X(cast(Listing.exact_location, Geometry("POINT", srid=4326))),
            ST_Y(cast(Listing.exact_location, Geometry("POINT", srid=4326))),
            promotion_boosted_at_expression(),
            promotion_ends_at_expression(),
        )
        .join(User, User.id == Listing.owner_user_id)
        .outerjoin(ListingRoomDetails, ListingRoomDetails.listing_id == Listing.id)
    )


def apply_search_filters(query: Select, payload: ListingSearchRequest) -> Select:
    price = primary_price_expression()
    bedrooms = bedroom_count_expression()
    if payload.query and payload.query.casefold() not in {"tenerife", "isla de tenerife"}:
        term = f"%{payload.query}%"
        query = query.where(or_(Listing.city.ilike(term), Listing.area.ilike(term)))
    if payload.city:
        query = query.where(Listing.city.ilike(f"%{payload.city}%"))
    if payload.area:
        query = query.where(Listing.area.ilike(f"%{payload.area}%"))
    if payload.rentalMode:
        query = query.where(Listing.rental_mode == payload.rentalMode)
    if payload.minPrice is not None:
        query = query.where(price >= payload.minPrice)
    if payload.maxPrice is not None:
        query = query.where(price <= payload.maxPrice)
    if payload.roomType:
        query = query.where(Listing.room_type == payload.roomType)
    if payload.roomTypes:
        query = query.where(Listing.room_type.in_(payload.roomTypes))
    if payload.bedroomCounts:
        exact = [int(value) for value in payload.bedroomCounts if value != "10+"]
        predicates = []
        if exact:
            predicates.append(bedrooms.in_(exact))
        if "10+" in payload.bedroomCounts:
            predicates.append(bedrooms > 10)
        query = query.where(or_(*predicates))
    if payload.availableFrom:
        query = query.where(
            (Listing.available_from.is_(None)) | (Listing.available_from <= payload.availableFrom),
            (Listing.available_until.is_(None)) | (Listing.available_until >= payload.availableFrom),
        )
    if payload.maxMinimumStayMonths is not None:
        query = query.where(
            Listing.minimum_stay_months.is_not(None), Listing.minimum_stay_months <= payload.maxMinimumStayMonths
        )
    if payload.restrictions:
        query = query.where(Listing.restrictions.contains(payload.restrictions))
    if payload.tenantRequirement:
        query = query.where(Listing.tenant_requirement == payload.tenantRequirement)
    if payload.bathroom:
        query = query.where(Listing.bathroom == payload.bathroom)
    if payload.kitchen:
        query = query.where(Listing.kitchen == payload.kitchen)
    if payload.furnished is not None:
        query = query.where(Listing.furnished == payload.furnished)
    if payload.billsIncluded is not None:
        query = query.where(Listing.bills_included == payload.billsIncluded)
    if payload.deposit == "Sin fianza":
        query = query.where(Listing.deposit_amount == 0)
    elif payload.deposit == "Hasta 1 mes":
        query = query.where(Listing.deposit_amount <= price)
    elif payload.deposit == "Más de 1 mes":
        query = query.where(Listing.deposit_amount > price)
    if payload.minRoomSizeM2 is not None:
        query = query.where(Listing.room_size_m2 >= payload.minRoomSizeM2)
    if payload.maxRoomSizeM2 is not None:
        query = query.where(Listing.room_size_m2 <= payload.maxRoomSizeM2)
    if payload.shower:
        query = query.where(Listing.shower == payload.shower)
    if payload.currentResidents is not None:
        query = query.where(Listing.current_residents == payload.currentResidents)
    if payload.minCurrentResidents is not None:
        query = query.where(Listing.current_residents >= payload.minCurrentResidents)
    if payload.roomCapacity is not None:
        query = query.where(func.coalesce(ListingRoomDetails.room_capacity_v2, Listing.room_capacity) == payload.roomCapacity)
    if payload.maxMinimumNights is not None:
        query = query.where(Listing.minimum_nights.is_not(None), Listing.minimum_nights <= payload.maxMinimumNights)
    if payload.availableUntil:
        query = query.where((Listing.available_until.is_(None)) | (Listing.available_until >= payload.availableUntil))
    for column, value in (
        (Listing.smoking_allowed, payload.smokingAllowed),
        (Listing.pets_allowed, payload.petsAllowed),
        (Listing.children_allowed, payload.childrenAllowed),
        (Listing.empadronamiento_allowed, payload.empadronamientoAllowed),
    ):
        if value is not None:
            query = query.where(column == value)
    if payload.minHomeSizeM2 is not None:
        query = query.where(ListingRoomDetails.home_size_m2 >= payload.minHomeSizeM2)
    if payload.maxHomeSizeM2 is not None:
        query = query.where(ListingRoomDetails.home_size_m2 <= payload.maxHomeSizeM2)
    if payload.minBathroomCount is not None:
        query = query.where(ListingRoomDetails.bathroom_count >= payload.minBathroomCount)
    if payload.rentalUnit:
        query = query.where(ListingRoomDetails.rental_unit == payload.rentalUnit)
    if payload.bedType:
        query = query.where(func.coalesce(ListingRoomDetails.bed_type_v2, ListingRoomDetails.bed_type) == payload.bedType)
    if payload.minBedCount is not None:
        query = query.where(ListingRoomDetails.bed_count >= payload.minBedCount)
    if payload.currentRoomResidents is not None:
        query = query.where(ListingRoomDetails.current_room_residents == payload.currentRoomResidents)
    if payload.maxCurrentRoomResidents is not None:
        query = query.where(ListingRoomDetails.current_room_residents <= payload.maxCurrentRoomResidents)
    if payload.minAvailableSpots is not None:
        query = query.where(
            ListingRoomDetails.current_room_residents.is_not(None),
            func.coalesce(ListingRoomDetails.room_capacity_v2, Listing.room_capacity).is_not(None),
            func.coalesce(ListingRoomDetails.room_capacity_v2, Listing.room_capacity)
            - ListingRoomDetails.current_room_residents
            >= payload.minAvailableSpots,
        )
    if payload.toilet:
        query = query.where(ListingRoomDetails.toilet == payload.toilet)
    if payload.householdGender:
        query = query.where(ListingRoomDetails.household_gender == payload.householdGender)
    if payload.householdHasChildren is not None:
        query = query.where(ListingRoomDetails.household_has_children == payload.householdHasChildren)
    if payload.heatingType:
        query = query.where(ListingRoomDetails.heating_type == payload.heatingType)
    if payload.accessible is not None:
        query = query.where(ListingRoomDetails.accessible == payload.accessible)
    if payload.floor:
        query = query.where(ListingRoomDetails.floor == payload.floor)
    if payload.couplesAllowed is not None:
        query = query.where(ListingRoomDetails.couples_allowed == payload.couplesAllowed)
    if payload.acceptedTenantTypes:
        query = query.where(
            or_(
                *(ListingRoomDetails.accepted_tenant_types.contains([tenant_type]) for tenant_type in payload.acceptedTenantTypes)
            )
        )
    if payload.publishedWithinDays is not None:
        query = query.where(Listing.published_at >= datetime.now(UTC) - timedelta(days=payload.publishedWithinDays))
    if payload.advertiserType:
        query = query.where(Listing.advertiser_type == payload.advertiserType)
    if payload.amenities:
        amenity_filter_aliases = {
            "Balcón": ("Balcón", "Balcón disponible"),
            "Lavadora": ("Lavadora", "Lavadora individual", "Lavadora compartida"),
        }
        for amenity in payload.amenities:
            aliases = amenity_filter_aliases.get(amenity, (amenity,))
            query = query.where(or_(*(Listing.amenities.contains([alias]) for alias in aliases)))
    if payload.minLongitude is not None:
        bbox = ST_MakeEnvelope(
            payload.minLongitude, payload.minLatitude, payload.maxLongitude, payload.maxLatitude, 4326
        )
        query = query.where(ST_Intersects(Listing.location, cast(bbox, Geography("POLYGON", srid=4326))))
    if payload.center and payload.radiusKm is not None:
        query = query.where(
            ST_DWithin(
                Listing.location, point(payload.center.longitude, payload.center.latitude), payload.radiusKm * 1000
            )
        )
    if payload.polygon:
        wkt = "POLYGON((" + ", ".join(f"{item.longitude} {item.latitude}" for item in payload.polygon) + "))"
        polygon = ST_GeomFromText(wkt, 4326)
        query = query.where(ST_Intersects(Listing.location, cast(polygon, Geography("POLYGON", srid=4326))))
    return query


def apply_search_order(query: Select, payload: ListingSearchRequest) -> Select:
    price = primary_price_expression()
    # Active TOP is a hard server-owned tier. Ordinary listings can be newer,
    # freshly imported, or newly published by a user, but they must never sort
    # ahead of an active promotion. Boost time only orders listings *within*
    # the TOP tier; the requested public sort then applies within each tier.
    promotion_tier = active_promotion_expression().desc()
    promotion_recency = promotion_boosted_at_expression().desc().nullslast()
    if payload.sort == "price_asc":
        return query.order_by(promotion_tier, promotion_recency, price.asc().nullslast(), Listing.id)
    if payload.sort == "price_desc":
        return query.order_by(promotion_tier, promotion_recency, price.desc().nullslast(), Listing.id)
    if payload.sort == "oldest":
        return query.order_by(promotion_tier, promotion_recency, Listing.created_at.asc(), Listing.id)
    return query.order_by(promotion_tier, promotion_recency, Listing.created_at.desc(), Listing.id)


async def search_public(session: AsyncSession, payload: ListingSearchRequest) -> ListingSearchResponse:
    filtered = apply_search_filters(visible_query(), payload)
    total = await session.scalar(select(func.count()).select_from(filtered.order_by(None).subquery()))
    rows = (
        await session.execute(apply_search_order(filtered, payload).limit(payload.limit).offset(payload.offset))
    ).all()
    return ListingSearchResponse(
        items=[response_from(row) for row in rows],
        total=total or 0,
        limit=payload.limit,
        offset=payload.offset,
    )


def _card_sort_components(sort: str, favorite_ids: list[UUID]):
    promoted = case((active_promotion_expression(), 1), else_=0)
    boosted = func.coalesce(func.extract("epoch", promotion_boosted_at_expression()), 0)
    created = func.extract("epoch", Listing.created_at)
    components: list[tuple[Any, bool]] = [(promoted, False), (boosted, False)]
    if sort.startswith("saved_"):
        components.append((case((Listing.id.in_(favorite_ids), 1), else_=0), False))
        components.append((created, sort == "saved_old"))
    if sort.startswith("price_"):
        price = primary_price_expression()
        components.extend([(case((price.is_(None), 1), else_=0), True), (func.coalesce(price, 0), sort == "price_asc")])
    elif sort == "reduced":
        price = primary_price_expression()
        components.extend([(case((price.is_(None), 1), else_=0), True), (func.coalesce(price, 0), True), (Listing.views, False)])
    elif sort.startswith("sqm_"):
        price = primary_price_expression()
        size = Listing.room_size_m2
        components.extend([(case((or_(price.is_(None), size.is_(None), size <= 0), 1), else_=0), True),
                           (cast(func.coalesce(price, 0) / func.greatest(1, func.coalesce(size, 1)), Float), sort == "sqm_asc")])
    elif sort.startswith("area_"):
        size = Listing.room_size_m2
        components.extend([(case((size.is_(None), 1), else_=0), True), (func.coalesce(size, 0), sort == "area_asc")])
    elif sort.startswith("floor_"):
        floor = ListingRoomDetails.floor
        rank = case((floor == "basement", 0), (floor == "1", 1), (floor == "2", 2),
                    (floor == "3", 3), (floor == "4+", 4), (floor == "top", 5))
        components.extend([(case((floor.is_(None), 1), else_=0), True),
                           (func.coalesce(rank, 0), sort == "floor_asc")])
    elif not sort.startswith("saved_"):
        components.append((created, sort == "oldest"))
    components.append((Listing.id, True))
    return components


def card_from_detail(detail: ListingResponse) -> ListingCardResponse:
    return ListingCardResponse(
        id=detail.id, title=detail.title, city=detail.city, area=detail.area,
        approximateAddress=detail.approximateAddress, rentalMode=detail.rentalMode,
        price=detail.price, roomType=detail.roomType, currentResidents=detail.currentResidents,
        roomCapacity=detail.roomCapacity, bedroomCount=detail.bedroomCount,
        roomSizeM2=detail.roomSizeM2, availableFrom=detail.availableFrom,
        billsIncluded=detail.billsIncluded, restrictions=detail.restrictions,
        advertiserType=detail.advertiserType, isExternal=detail.isExternal,
        sourceUrl=detail.sourceUrl, primarySource=detail.primarySource,
        sourcePriceText=detail.sourcePriceText, pricePeriod=detail.pricePeriod,
        priceIsFrom=detail.priceIsFrom, publishedAt=detail.publishedAt,
        promoted=detail.promoted, coverImageUrl=detail.coverImageUrl,
        imageUrls=detail.imageUrls,
        description=detail.description[:240],
    )


def _cursor_fingerprint(payload: ListingCardSearchRequest) -> str:
    filters = payload.model_dump(mode="json", exclude={"cursor", "limit", "offset"})
    return sha256(json.dumps(filters, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:20]


def _decode_cursor(cursor: str, fingerprint: str, component_count: int) -> tuple[list, str]:
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        if data["q"] != fingerprint or data["d"] not in {"after", "before"} or not isinstance(data["k"], list) or len(data["k"]) != component_count:
            raise ValueError("cursor does not match search")
        values = data["k"]
        values[-1] = UUID(values[-1])
        if not all(type(value) in (int, float) and math.isfinite(value) for value in values[:-1]):
            raise ValueError("invalid cursor values")
        return values, data["d"]
    except (KeyError, TypeError, ValueError, OverflowError, binascii.Error) as exc:
        raise HTTPException(400, "Invalid search cursor") from exc


def _seek(components: list, values: list, direction: str):
    branches = []
    for index, (expression, ascending) in enumerate(components):
        preceding = [components[prior][0] == values[prior] for prior in range(index)]
        comparison = expression > values[index] if ascending == (direction == "after") else expression < values[index]
        branches.append(and_(*preceding, comparison))
    return or_(*branches)


async def search_public_cards(session: AsyncSession, payload: ListingCardSearchRequest) -> ListingCardSearchResponse:
    filtered = apply_search_filters(visible_query(), payload)
    count_query = filtered.with_only_columns(Listing.id).order_by(None).subquery()
    total = await session.scalar(select(func.count()).select_from(count_query)) or 0
    components = _card_sort_components(payload.sort, payload.favoriteIds)
    fingerprint = _cursor_fingerprint(payload)
    direction = "after"
    if payload.cursor:
        values, direction = _decode_cursor(payload.cursor, fingerprint, len(components))
        filtered = filtered.where(_seek(components, values, direction))
    gallery_asset_ids = image_asset_ids_subquery()
    columns = [
        Listing.id.label("id"), Listing.title.label("title"), Listing.city.label("city"),
        Listing.area.label("area"), Listing.approximate_address.label("approximateAddress"),
        Listing.rental_mode.label("rentalMode"), primary_price_expression().label("price"),
        Listing.room_type.label("roomType"), Listing.current_residents.label("currentResidents"),
        func.coalesce(ListingRoomDetails.room_capacity_v2, Listing.room_capacity).label("roomCapacity"),
        bedroom_count_expression().label("bedroomCount"),
        Listing.room_size_m2.label("roomSizeM2"), Listing.available_from.label("availableFrom"),
        Listing.bills_included.label("billsIncluded"), Listing.restrictions.label("restrictions"),
        Listing.advertiser_type.label("advertiserType"), Listing.is_external.label("isExternal"),
        Listing.primary_source_url.label("sourceUrl"), Listing.primary_source.label("primarySource"),
        Listing.source_price_text.label("sourcePriceText"), Listing.source_price_period.label("pricePeriod"),
        Listing.source_price_is_from.label("priceIsFrom"), Listing.published_at.label("publishedAt"),
        active_promotion_expression().label("promoted"),
        gallery_asset_ids.label("_imageAssetIds"), Listing.external_image_urls.label("_externalImageUrls"),
        func.left(Listing.description, 240).label("description"),
    ]
    card_columns = len(columns)
    query = filtered.with_only_columns(*columns, *(expression.label(f"seek_{index}") for index, (expression, _) in enumerate(components)))
    query = query.order_by(*(expression.asc() if ascending == (direction == "after") else expression.desc() for expression, ascending in components))
    rows = list((await session.execute(query.limit(payload.limit + 1))).all())
    has_more = len(rows) > payload.limit
    rows = rows[:payload.limit]
    if direction == "before":
        rows.reverse()
    items: list[ListingCardResponse] = []
    for row in rows:
        card_data = {
            str(key): (str(value) if key == "id" else value)
            for key, value in list(row._mapping.items())[:card_columns]
        }
        asset_ids = card_data.pop("_imageAssetIds", None) or []
        external_image_urls = card_data.pop("_externalImageUrls", None) or []
        image_urls = (
            [f"/api/v1/media/{asset_id}" for asset_id in asset_ids[:MAX_LISTING_PHOTOS]]
            or list(external_image_urls)[:MAX_LISTING_PHOTOS]
        )
        card_data["coverImageUrl"] = image_urls[0] if image_urls else None
        card_data["imageUrls"] = image_urls
        items.append(ListingCardResponse.model_validate(card_data))
    def encode(row, cursor_direction):
        values = [str(value) if isinstance(value, UUID) else float(value) if value is not None else 0 for value in row[card_columns:]]
        return base64.urlsafe_b64encode(json.dumps({"q": fingerprint, "d": cursor_direction, "k": values}, separators=(",", ":")).encode()).decode().rstrip("=")
    return ListingCardSearchResponse(
        items=items, total=total,
        nextCursor=encode(rows[-1], "after") if rows and (has_more if direction == "after" else bool(payload.cursor)) else None,
        previousCursor=encode(rows[0], "before") if rows and (bool(payload.cursor) if direction == "after" else has_more) else None,
    )


async def search_public_map(session: AsyncSession, payload: ListingMapRequest) -> ListingMapResponse:
    # A viewport is mandatory. Grid dimensions are derived from its size, so the
    # number of returned buckets is bounded even when the viewport covers Spain.
    bounded = payload.model_copy(update={
        "minLatitude": payload.south, "maxLatitude": payload.north,
        "minLongitude": payload.west, "maxLongitude": payload.east,
    })
    filtered = apply_search_filters(visible_query(), bounded)
    longitude = ST_X(cast(Listing.location, Geometry("POINT", srid=4326)))
    latitude = ST_Y(cast(Listing.location, Geometry("POINT", srid=4326)))
    max_markers = 300
    if payload.zoom >= 13:
        columns = [Listing.id, latitude, longitude, primary_price_expression(), active_promotion_expression(), Listing.is_external, Listing.primary_source_url]
        rows = (await session.execute(filtered.with_only_columns(*columns).order_by(Listing.id).limit(max_markers + 1))).all()
        if len(rows) <= max_markers:
            return ListingMapResponse(items=[ListingMarker(
                id=str(row[0]), latitude=row[1], longitude=row[2], price=row[3],
                promoted=row[4], isExternal=row[5], sourceUrl=row[6],
            ) for row in rows if row[1] is not None and row[2] is not None])
    lon_cell = (payload.east - payload.west) / 20
    lat_cell = (payload.north - payload.south) / 20
    base = filtered.with_only_columns(
        latitude.label("lat"),
        longitude.label("lon"),
        active_promotion_expression().label("promoted"),
    ).subquery()
    x = func.least(19, func.greatest(0, func.floor((base.c.lon - payload.west) / lon_cell)))
    y = func.least(19, func.greatest(0, func.floor((base.c.lat - payload.south) / lat_cell)))
    clusters = (
        select(
            x.label("x"),
            y.label("y"),
            func.avg(base.c.lat),
            func.avg(base.c.lon),
            func.count(),
            func.bool_or(base.c.promoted),
        )
        .where(base.c.lat.is_not(None), base.c.lon.is_not(None))
        .group_by(x, y)
    )
    rows = (await session.execute(clusters)).all()
    return ListingMapResponse(items=[ClusterMarker(
        id=f"{int(row[0])}:{int(row[1])}",
        latitude=float(row[2]),
        longitude=float(row[3]),
        count=row[4],
        promoted=bool(row[5]),
    ) for row in rows])


async def register_view(listing: Listing, viewer_key: str, session: AsyncSession) -> bool:
    result = await session.execute(
        insert(ListingView)
        .values(listing_id=listing.id, viewer_key=viewer_key, view_date=datetime.now(UTC).date())
        .on_conflict_do_nothing(constraint="uq_listing_views_daily")
    )
    if getattr(result, "rowcount", 0):
        await session.execute(update(Listing).where(Listing.id == listing.id).values(views=Listing.views + 1))
        await session.commit()
        return True
    return False


def anonymous_viewer_key(visitor_token: str) -> str:
    return hmac_new(get_settings().jwt_secret.encode(), visitor_token.encode(), sha256).hexdigest()
