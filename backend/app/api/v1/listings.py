from __future__ import annotations

from secrets import token_urlsafe
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import get_settings
from ...db.session import get_session
from ...models import Listing, ListingImage, MediaAsset, User
from ...repositories.listings import (
    anonymous_viewer_key,
    owned_query,
    owned_response_from,
    register_view,
    response_from,
    search_public,
    visible_query,
)
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
from ...services.listings import (
    create_listing as create_listing_service,
    delete_listing as delete_listing_service,
    renew_listing as renew_listing_service,
    replace_listing_images as replace_listing_images_service,
    update_listing as update_listing_service,
)
from ..dependencies import current_user, optional_user, require_role

router = APIRouter(prefix="/listings", tags=["listings"])


@router.get("", response_model=list[ListingResponse])
async def list_listings(
    city: str | None = None,
    area: str | None = None,
    rental_mode: str | None = Query(default=None, alias="rentalMode"),
    min_price: int | None = Query(default=None, ge=0, alias="minPrice"),
    max_price: int | None = Query(default=None, ge=0, alias="maxPrice"),
    session: AsyncSession = Depends(get_session),
):
    payload = ListingSearchRequest(
        city=city,
        area=area,
        rentalMode=rental_mode,
        minPrice=min_price,
        maxPrice=max_price,
        limit=100,
    )
    return (await search_public(session, payload)).items


@router.post("/search", response_model=ListingSearchResponse)
async def search_listings(payload: ListingSearchRequest, session: AsyncSession = Depends(get_session)):
    return await search_public(session, payload)


@router.get("/mine", response_model=list[OwnedListingResponse])
async def list_my_listings(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    query = owned_query().where(Listing.deleted_at.is_(None))
    if user.role != "admin":
        query = query.where(Listing.owner_user_id == user.id)
    rows = (await session.execute(query.order_by(Listing.created_at.desc()))).all()
    return [owned_response_from(row) for row in rows]


@router.get("/{listing_id}", response_model=ListingResponse)
async def get_listing(
    listing_id: UUID,
    response: Response,
    visitor_token: str | None = Cookie(default=None, alias="listing_visitor"),
    user: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_session),
):
    row = (await session.execute(visible_query().where(Listing.id == listing_id))).one_or_none()
    if not row:
        raise HTTPException(404, "Listing not found")
    if user:
        viewer_key = f"user:{user.id}"
    else:
        if not visitor_token:
            visitor_token = token_urlsafe(32)
            settings = get_settings()
            response.set_cookie(
                "listing_visitor",
                visitor_token,
                httponly=True,
                secure=settings.is_production,
                samesite="none" if settings.is_production else "lax",
                max_age=90 * 24 * 60 * 60,
                path="/api/v1/listings",
            )
        viewer_key = anonymous_viewer_key(visitor_token)
    if await register_view(row[0], viewer_key, session):
        row = (await session.execute(visible_query().where(Listing.id == listing_id))).one()
    return response_from(row)


@router.post("", response_model=OwnedListingResponse, status_code=status.HTTP_201_CREATED)
async def create_listing(
    payload: ListingWrite,
    user: User = Depends(require_role("host", "admin")),
    session: AsyncSession = Depends(get_session),
):
    return await create_listing_service(payload, user, session)


@router.patch("/{listing_id}", response_model=OwnedListingResponse)
async def update_listing(
    listing_id: UUID,
    payload: ListingPatch,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return await update_listing_service(listing_id, payload, user, session)


@router.post("/{listing_id}/renew", response_model=OwnedListingResponse)
async def renew_listing(
    listing_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return await renew_listing_service(listing_id, user, session)


@router.delete("/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_listing(
    listing_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await delete_listing_service(listing_id, user, session)


@router.get("/{listing_id}/images", response_model=list[ListingImageResponse])
async def list_listing_images(
    listing_id: UUID,
    user: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_session),
):
    listing = await session.get(Listing, listing_id)
    owner_or_admin = listing and user and (listing.owner_user_id == user.id or user.role == "admin")
    if not listing or listing.deleted_at is not None or (listing.status != "published" and not owner_or_admin):
        raise HTTPException(404, "Listing not found")
    rows = (
        await session.execute(
            select(ListingImage, MediaAsset)
            .join(MediaAsset, MediaAsset.id == ListingImage.media_asset_id)
            .where(ListingImage.listing_id == listing.id, MediaAsset.deleted_at.is_(None))
            .order_by(ListingImage.sort_order)
        )
    ).all()
    return [
        ListingImageResponse(
            assetId=asset.id,
            url=f"/api/v1/media/{asset.id}",
            sortOrder=image.sort_order,
            isCover=image.is_cover,
        )
        for image, asset in rows
    ]


@router.put("/{listing_id}/images", response_model=list[ListingImageResponse])
async def replace_listing_images(
    listing_id: UUID,
    payload: ListingImagesRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return await replace_listing_images_service(listing_id, payload, user, session)
