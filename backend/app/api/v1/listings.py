import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2 import Geometry
from geoalchemy2.functions import (
    ST_AsGeoJSON,
    ST_DWithin,
    ST_GeomFromText,
    ST_MakeEnvelope,
    ST_MakePoint,
    ST_SetSRID,
    ST_Within,
)
from sqlalchemy import Select, cast, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...models import Listing, ListingImage, MediaAsset, User
from ...schemas.listings import (
    ListingImageResponse,
    ListingImagesRequest,
    ListingPatch,
    ListingResponse,
    ListingSearchRequest,
    ListingSearchResponse,
    ListingWrite,
    OwnedListingResponse,
)
from ..dependencies import current_user, require_role

router = APIRouter(prefix="/listings", tags=["listings"])


def point(longitude: float, latitude: float):
    return ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)


def response_from(row: tuple[Listing, str]) -> ListingResponse:
    listing, geojson = row
    coordinates = json.loads(geojson)["coordinates"]
    price = listing.monthly_price if listing.rental_mode == "long" else listing.nightly_price
    return ListingResponse(
        id=str(listing.id), ownerUserId=str(listing.owner_user_id), title=listing.title,
        city=listing.city, area=listing.area, approximateAddress=listing.approximate_address,
        rentalMode=listing.rental_mode, monthlyPrice=listing.monthly_price, nightlyPrice=listing.nightly_price, weeklyPrice=listing.weekly_price,
        price=price, cadence="mes" if listing.rental_mode == "long" else "noche",
        roomType=listing.room_type, availableFrom=listing.available_from, availableUntil=listing.available_until,
        minimumStayMonths=listing.minimum_stay_months, minimumNights=listing.minimum_nights,
        depositAmount=listing.deposit_amount, billsIncluded=listing.bills_included, bathroom=listing.bathroom,
        kitchen=listing.kitchen, furnished=listing.furnished, roomSizeM2=listing.room_size_m2,
        bedroomCount=listing.bedroom_count, currentResidents=listing.current_residents, roomCapacity=listing.room_capacity,
        shower=listing.shower, tenantRequirement=listing.tenant_requirement, smokingAllowed=listing.smoking_allowed,
        petsAllowed=listing.pets_allowed, childrenAllowed=listing.children_allowed,
        empadronamientoAllowed=listing.empadronamiento_allowed, restrictions=listing.restrictions, amenities=listing.amenities,
        status=listing.status, longitude=coordinates[0], latitude=coordinates[1], description=listing.description,
        homeDescription=listing.home_description, advertiserType=listing.advertiser_type, source=listing.source,
        publishedAt=listing.published_at, expiresAt=listing.expires_at, views=listing.views, closedReason=listing.closed_reason,
        createdAt=listing.created_at, updatedAt=listing.updated_at,
    )


def owned_response_from(row: tuple[Listing, str, str | None]) -> OwnedListingResponse:
    listing, public_geojson, exact_geojson = row
    public = response_from((listing, public_geojson)).model_dump()
    exact_coordinates = json.loads(exact_geojson)["coordinates"] if exact_geojson else None
    return OwnedListingResponse(
        **public,
        street=listing.street,
        postcode=listing.postcode,
        exactLatitude=exact_coordinates[1] if exact_coordinates else None,
        exactLongitude=exact_coordinates[0] if exact_coordinates else None,
    )


def visible_query() -> Select:
    return select(Listing, ST_AsGeoJSON(Listing.location)).where(
        Listing.status == "published",
        Listing.deleted_at.is_(None),
        (Listing.expires_at.is_(None)) | (Listing.expires_at > func.now()),
    )


def owned_query() -> Select:
    return select(Listing, ST_AsGeoJSON(Listing.location), ST_AsGeoJSON(Listing.exact_location))


def search_filters(query: Select, payload: ListingSearchRequest) -> Select:
    if payload.city:
        query = query.where(Listing.city.ilike(f"%{payload.city.strip()}%"))
    if payload.area:
        query = query.where(Listing.area.ilike(f"%{payload.area.strip()}%"))
    if payload.rentalMode:
        query = query.where(Listing.rental_mode == payload.rentalMode)
    if payload.minPrice is not None:
        query = query.where((Listing.monthly_price >= payload.minPrice) | (Listing.nightly_price >= payload.minPrice))
    if payload.maxPrice is not None:
        query = query.where((Listing.monthly_price <= payload.maxPrice) | (Listing.nightly_price <= payload.maxPrice))
    if payload.minLongitude is not None:
        bbox = ST_MakeEnvelope(payload.minLongitude, payload.minLatitude, payload.maxLongitude, payload.maxLatitude, 4326)
        query = query.where(ST_Within(cast(Listing.location, Geometry("POINT", srid=4326)), bbox))
    if payload.center:
        query = query.where(ST_DWithin(Listing.location, point(payload.center.longitude, payload.center.latitude), payload.radiusKm * 1000))
    if payload.polygon:
        wkt = "POLYGON((" + ", ".join(f"{item.longitude} {item.latitude}" for item in payload.polygon) + "))"
        polygon = ST_GeomFromText(wkt, 4326)
        query = query.where(ST_Within(cast(Listing.location, Geometry("POINT", srid=4326)), polygon))
    return query


@router.get("", response_model=list[ListingResponse])
async def list_listings(
    city: str | None = None, area: str | None = None, rental_mode: str | None = Query(default=None, alias="rentalMode"),
    min_price: int | None = Query(default=None, ge=0, alias="minPrice"),
    max_price: int | None = Query(default=None, ge=0, alias="maxPrice"), session: AsyncSession = Depends(get_session),
):
    query = visible_query()
    if city:
        query = query.where(Listing.city.ilike(f"%{city.strip()}%"))
    if area:
        query = query.where(Listing.area.ilike(f"%{area.strip()}%"))
    if rental_mode in {"long", "holiday"}:
        query = query.where(Listing.rental_mode == rental_mode)
    if min_price is not None:
        query = query.where((Listing.monthly_price >= min_price) | (Listing.nightly_price >= min_price))
    if max_price is not None:
        query = query.where((Listing.monthly_price <= max_price) | (Listing.nightly_price <= max_price))
    return [response_from(row) for row in (await session.execute(query.order_by(Listing.created_at.desc()))).all()]


@router.post("/search", response_model=ListingSearchResponse)
async def search_listings(payload: ListingSearchRequest, session: AsyncSession = Depends(get_session)):
    query = search_filters(visible_query(), payload)
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    price = func.coalesce(Listing.monthly_price, Listing.nightly_price)
    ordering = {
        "newest": Listing.created_at.desc(),
        "price_asc": price.asc(),
        "price_desc": price.desc(),
    }[payload.sort]
    rows = (await session.execute(query.order_by(ordering, Listing.id).limit(payload.limit).offset(payload.offset))).all()
    return ListingSearchResponse(items=[response_from(row) for row in rows], total=total or 0, limit=payload.limit, offset=payload.offset)


@router.get("/mine", response_model=list[OwnedListingResponse])
async def list_my_listings(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    query = owned_query()
    if user.role != "admin":
        query = query.where(Listing.owner_user_id == user.id)
    return [owned_response_from(row) for row in (await session.execute(query.order_by(Listing.created_at.desc()))).all()]


@router.get("/{listing_id}", response_model=ListingResponse)
async def get_listing(listing_id: UUID, session: AsyncSession = Depends(get_session)):
    row = (await session.execute(visible_query().where(Listing.id == listing_id))).one_or_none()
    if not row:
        raise HTTPException(404, "Listing not found")
    return response_from(row)


@router.post("", response_model=OwnedListingResponse, status_code=status.HTTP_201_CREATED)
async def create_listing(
    payload: ListingWrite, user: User = Depends(require_role("host", "admin")), session: AsyncSession = Depends(get_session)
):
    listing = Listing(
        owner_user_id=user.id, title=payload.title.strip(), city=payload.city.strip(), area=payload.area.strip(),
        street=payload.street.strip(), postcode=payload.postcode.strip(),
        approximate_address=payload.approximateAddress.strip(), rental_mode=payload.rentalMode,
        monthly_price=payload.monthlyPrice, nightly_price=payload.nightlyPrice, weekly_price=payload.weeklyPrice,
        room_type=payload.roomType, available_from=payload.availableFrom, available_until=payload.availableUntil,
        minimum_stay_months=payload.minimumStayMonths, minimum_nights=payload.minimumNights,
        deposit_amount=payload.depositAmount, bills_included=payload.billsIncluded, bathroom=payload.bathroom,
        kitchen=payload.kitchen, furnished=payload.furnished, room_size_m2=payload.roomSizeM2,
        bedroom_count=payload.bedroomCount, current_residents=payload.currentResidents, room_capacity=payload.roomCapacity,
        shower=payload.shower, tenant_requirement=payload.tenantRequirement, smoking_allowed=payload.smokingAllowed,
        pets_allowed=payload.petsAllowed, children_allowed=payload.childrenAllowed,
        empadronamiento_allowed=payload.empadronamientoAllowed, restrictions=payload.restrictions, amenities=payload.amenities,
        location=point(payload.longitude, payload.latitude),
        exact_location=(point(payload.exactLongitude, payload.exactLatitude) if payload.exactLongitude is not None else None),
        description=payload.description.strip(), home_description=payload.homeDescription.strip(), advertiser_type=payload.advertiserType,
        source=payload.source.strip() if payload.source else None, expires_at=payload.expiresAt, status="pending",
    )
    session.add(listing)
    await session.commit()
    row = (await session.execute(owned_query().where(Listing.id == listing.id))).one()
    return owned_response_from(row)


@router.patch("/{listing_id}", response_model=OwnedListingResponse)
async def update_listing(
    listing_id: UUID, payload: ListingPatch, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
):
    listing = await session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")
    if listing.owner_user_id != user.id and user.role != "admin":
        raise HTTPException(403, "Forbidden")
    changes = payload.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"] not in {"draft", "pending", "hidden", "closed"} and user.role != "admin":
        raise HTTPException(403, "Only an administrator can publish or reject listings")
    mapping = {
        "approximateAddress": "approximate_address", "monthlyPrice": "monthly_price", "nightlyPrice": "nightly_price",
        "weeklyPrice": "weekly_price", "roomType": "room_type", "availableFrom": "available_from",
        "availableUntil": "available_until", "minimumStayMonths": "minimum_stay_months", "minimumNights": "minimum_nights",
        "depositAmount": "deposit_amount", "billsIncluded": "bills_included", "roomSizeM2": "room_size_m2",
        "bedroomCount": "bedroom_count", "currentResidents": "current_residents", "roomCapacity": "room_capacity",
        "tenantRequirement": "tenant_requirement", "smokingAllowed": "smoking_allowed", "petsAllowed": "pets_allowed",
        "childrenAllowed": "children_allowed", "empadronamientoAllowed": "empadronamiento_allowed",
        "homeDescription": "home_description", "advertiserType": "advertiser_type", "expiresAt": "expires_at",
    }
    latitude, longitude = changes.pop("latitude", None), changes.pop("longitude", None)
    if latitude is not None or longitude is not None:
        if latitude is None or longitude is None:
            raise HTTPException(422, "latitude and longitude must be changed together")
        listing.location = point(longitude, latitude)
    exact_latitude, exact_longitude = changes.pop("exactLatitude", None), changes.pop("exactLongitude", None)
    if exact_latitude is not None or exact_longitude is not None:
        if exact_latitude is None or exact_longitude is None:
            raise HTTPException(422, "exactLatitude and exactLongitude must be changed together")
        listing.exact_location = point(exact_longitude, exact_latitude)
    for key, value in changes.items():
        setattr(listing, mapping.get(key, key), value.strip() if isinstance(value, str) else value)
    await session.commit()
    row = (await session.execute(owned_query().where(Listing.id == listing.id))).one()
    return owned_response_from(row)


@router.get("/{listing_id}/images", response_model=list[ListingImageResponse])
async def list_listing_images(listing_id: UUID, session: AsyncSession = Depends(get_session)):
    listing = await session.get(Listing, listing_id)
    if not listing or listing.status != "published":
        raise HTTPException(404, "Listing not found")
    rows = (
        await session.execute(
            select(ListingImage, MediaAsset).join(MediaAsset, MediaAsset.id == ListingImage.media_asset_id).where(
                ListingImage.listing_id == listing.id, MediaAsset.deleted_at.is_(None)
            ).order_by(ListingImage.sort_order)
        )
    ).all()
    return [
        ListingImageResponse(assetId=asset.id, url=f"/api/v1/media/{asset.id}", sortOrder=image.sort_order, isCover=image.is_cover)
        for image, asset in rows
    ]


@router.put("/{listing_id}/images", response_model=list[ListingImageResponse])
async def replace_listing_images(
    listing_id: UUID, payload: ListingImagesRequest, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
):
    listing = await session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")
    if listing.owner_user_id != user.id and user.role != "admin":
        raise HTTPException(403, "Forbidden")
    assets = (
        await session.scalars(select(MediaAsset).where(MediaAsset.id.in_(payload.assetIds), MediaAsset.deleted_at.is_(None)))
    ).all()
    if len(assets) != len(payload.assetIds) or any(asset.owner_id != user.id for asset in assets if user.role != "admin"):
        raise HTTPException(422, "Every image must be an active asset owned by the requester")
    await session.execute(delete(ListingImage).where(ListingImage.listing_id == listing.id))
    for sort_order, asset_id in enumerate(payload.assetIds):
        session.add(ListingImage(listing_id=listing.id, media_asset_id=asset_id, sort_order=sort_order, is_cover=sort_order == 0))
    await session.commit()
    return [
        ListingImageResponse(assetId=asset_id, url=f"/api/v1/media/{asset_id}", sortOrder=order, isCover=order == 0)
        for order, asset_id in enumerate(payload.assetIds)
    ]
