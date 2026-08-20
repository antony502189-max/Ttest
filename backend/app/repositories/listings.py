from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from hmac import new as hmac_new
from typing import Any

from geoalchemy2 import Geometry
from geoalchemy2.functions import (
    ST_X,
    ST_Y,
    ST_Covers,
    ST_DWithin,
    ST_GeomFromText,
    ST_MakeEnvelope,
    ST_MakePoint,
    ST_SetSRID,
)
from sqlalchemy import Select, case, cast, func, or_, select, update
from sqlalchemy.dialects.postgresql import aggregate_order_by, insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..models import Listing, ListingImage, ListingView, MediaAsset, User
from ..models.moderation import ListingPromotion, ListingRestriction, UserRestriction
from ..models.room_details import ListingRoomDetails
from ..schemas.listings import (
    ListingOwnerResponse,
    ListingResponse,
    ListingSearchRequest,
    ListingSearchResponse,
    OwnedListingResponse,
)


def point(longitude: float, latitude: float):
    return ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)


def primary_price_expression():
    return case((Listing.rental_mode == "holiday", Listing.nightly_price), else_=Listing.monthly_price)


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


def promotion_boosted_at_expression():
    return select(ListingPromotion.boosted_at).where(ListingPromotion.listing_id == Listing.id).scalar_subquery()


def response_from(row: Any) -> ListingResponse:
    listing, longitude, latitude, owner, asset_ids, room_details, boosted_at = row
    price = listing.nightly_price if listing.rental_mode == "holiday" else listing.monthly_price
    image_urls = [f"/api/v1/media/{asset_id}" for asset_id in (asset_ids or [])]
    if not image_urls:
        image_urls = listing.external_image_urls
    current_room_residents = room_details.current_room_residents if room_details else None
    available_spots = (
        max(0, listing.room_capacity - current_room_residents)
        if listing.room_capacity is not None and current_room_residents is not None
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
        allowContactForm=False if listing.is_external else owner.allow_contact_form,
        coverImageUrl=image_urls[0] if image_urls else None,
        imageUrls=image_urls,
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
        roomCapacity=listing.room_capacity,
        shower=listing.shower,
        tenantRequirement=listing.tenant_requirement,
        smokingAllowed=listing.smoking_allowed,
        petsAllowed=listing.pets_allowed,
        childrenAllowed=listing.children_allowed,
        empadronamientoAllowed=listing.empadronamiento_allowed,
        homeSizeM2=room_details.home_size_m2 if room_details else None,
        bathroomCount=room_details.bathroom_count if room_details else None,
        rentalUnit=room_details.rental_unit if room_details else None,
        bedType=room_details.bed_type if room_details else None,
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
    listing, longitude, latitude, owner, asset_ids, room_details, exact_longitude, exact_latitude, boosted_at = row
    public = response_from((listing, longitude, latitude, owner, asset_ids, room_details, boosted_at)).model_dump()
    return OwnedListingResponse(
        **public,
        street=listing.street,
        postcode=listing.postcode,
        exactLatitude=exact_latitude,
        exactLongitude=exact_longitude,
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
            ListingRestriction.ends_at > func.now(),
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
            Listing.deleted_at.is_(None),
            User.deleted_at.is_(None),
            User.blocked.is_(False),
            ~active_user_restriction,
            ~active_listing_restriction,
            (Listing.expires_at.is_(None)) | (Listing.expires_at > func.now()),
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
        query = query.where(Listing.room_capacity == payload.roomCapacity)
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
        query = query.where(ListingRoomDetails.bed_type == payload.bedType)
    if payload.minBedCount is not None:
        query = query.where(ListingRoomDetails.bed_count >= payload.minBedCount)
    if payload.currentRoomResidents is not None:
        query = query.where(ListingRoomDetails.current_room_residents == payload.currentRoomResidents)
    if payload.maxCurrentRoomResidents is not None:
        query = query.where(ListingRoomDetails.current_room_residents <= payload.maxCurrentRoomResidents)
    if payload.minAvailableSpots is not None:
        query = query.where(
            ListingRoomDetails.current_room_residents.is_not(None),
            Listing.room_capacity.is_not(None),
            Listing.room_capacity - ListingRoomDetails.current_room_residents >= payload.minAvailableSpots,
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
        query = query.where(Listing.amenities.contains(payload.amenities))
    if payload.minLongitude is not None:
        bbox = ST_MakeEnvelope(
            payload.minLongitude, payload.minLatitude, payload.maxLongitude, payload.maxLatitude, 4326
        )
        query = query.where(ST_Covers(bbox, cast(Listing.location, Geometry("POINT", srid=4326))))
    if payload.center and payload.radiusKm is not None:
        query = query.where(
            ST_DWithin(
                Listing.location, point(payload.center.longitude, payload.center.latitude), payload.radiusKm * 1000
            )
        )
    if payload.polygon:
        wkt = "POLYGON((" + ", ".join(f"{item.longitude} {item.latitude}" for item in payload.polygon) + "))"
        polygon = ST_GeomFromText(wkt, 4326)
        query = query.where(ST_Covers(polygon, cast(Listing.location, Geometry("POINT", srid=4326))))
    return query


def apply_search_order(query: Select, payload: ListingSearchRequest) -> Select:
    price = primary_price_expression()
    if payload.sort == "price_asc":
        return query.order_by(price.asc().nullslast(), Listing.id)
    if payload.sort == "price_desc":
        return query.order_by(price.desc().nullslast(), Listing.id)
    if payload.sort == "oldest":
        return query.order_by(Listing.created_at.asc(), Listing.id)
    return query.order_by(promotion_boosted_at_expression().desc().nullslast(), Listing.created_at.desc(), Listing.id)


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
