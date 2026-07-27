import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2.functions import ST_AsGeoJSON, ST_MakePoint, ST_SetSRID
from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...models import Listing, ListingImage, MediaAsset, User
from ...schemas.listings import ListingImageResponse, ListingImagesRequest, ListingPatch, ListingResponse, ListingWrite
from ..dependencies import current_user, require_role

router = APIRouter(prefix="/listings", tags=["listings"])


def point(longitude: float, latitude: float):
    return ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)


def response_from(row: tuple[Listing, str]) -> ListingResponse:
    listing, geojson = row
    coordinates = json.loads(geojson)["coordinates"]
    return ListingResponse(
        id=str(listing.id), ownerUserId=str(listing.owner_user_id), title=listing.title,
        city=listing.city, area=listing.area, approximateAddress=listing.approximate_address,
        rentalMode=listing.rental_mode, monthlyPrice=listing.monthly_price, nightlyPrice=listing.nightly_price,
        status=listing.status, longitude=coordinates[0], latitude=coordinates[1], description=listing.description,
        createdAt=listing.created_at, updatedAt=listing.updated_at,
    )


def visible_query() -> Select:
    return select(Listing, ST_AsGeoJSON(Listing.location)).where(Listing.status == "published")


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


@router.get("/{listing_id}", response_model=ListingResponse)
async def get_listing(listing_id: UUID, session: AsyncSession = Depends(get_session)):
    row = (await session.execute(visible_query().where(Listing.id == listing_id))).one_or_none()
    if not row:
        raise HTTPException(404, "Listing not found")
    return response_from(row)


@router.post("", response_model=ListingResponse, status_code=status.HTTP_201_CREATED)
async def create_listing(
    payload: ListingWrite, user: User = Depends(require_role("host", "admin")), session: AsyncSession = Depends(get_session)
):
    listing = Listing(
        owner_user_id=user.id, title=payload.title.strip(), city=payload.city.strip(), area=payload.area.strip(),
        approximate_address=payload.approximateAddress.strip(), rental_mode=payload.rentalMode,
        monthly_price=payload.monthlyPrice, nightly_price=payload.nightlyPrice, location=point(payload.longitude, payload.latitude),
        description=payload.description.strip(), status="pending",
    )
    session.add(listing)
    await session.commit()
    row = (await session.execute(select(Listing, ST_AsGeoJSON(Listing.location)).where(Listing.id == listing.id))).one()
    return response_from(row)


@router.patch("/{listing_id}", response_model=ListingResponse)
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
    mapping = {"approximateAddress": "approximate_address", "monthlyPrice": "monthly_price", "nightlyPrice": "nightly_price"}
    latitude, longitude = changes.pop("latitude", None), changes.pop("longitude", None)
    if latitude is not None or longitude is not None:
        if latitude is None or longitude is None:
            raise HTTPException(422, "latitude and longitude must be changed together")
        listing.location = point(longitude, latitude)
    for key, value in changes.items():
        setattr(listing, mapping.get(key, key), value.strip() if isinstance(value, str) else value)
    await session.commit()
    row = (await session.execute(select(Listing, ST_AsGeoJSON(Listing.location)).where(Listing.id == listing.id))).one()
    return response_from(row)


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
