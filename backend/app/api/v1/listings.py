from __future__ import annotations

from datetime import UTC, datetime
from secrets import token_urlsafe
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import get_settings
from ...core.http import client_ip
from ...db.session import get_session
from ...models import CatalogState, Listing, ListingImage, MediaAsset, User
from ...repositories.listings import (
    owned_query,
    owned_response_from,
    response_from,
    search_public,
    visible_query,
)
from ...schemas.listings import (
    CatalogVersionResponse,
    ListingImageResponse,
    ListingImagesRequest,
    ListingPatch,
    ListingResponse,
    ListingSearchRequest,
    ListingSearchResponse,
    ListingWrite,
    OwnedListingResponse,
)
from ...services.listing_limits import enforce_listing_creation_limits
from ...services.listing_views import anonymous_viewer_key, register_view
from ...services.listings import create_listing as create_listing_service
from ...services.listings import delete_listing as delete_listing_service
from ...services.listings import renew_listing as renew_listing_service
from ...services.listings import replace_listing_images as replace_listing_images_service
from ...services.listings import update_listing as update_listing_service
from ...services.moderation import (
    active_listing_restriction,
    active_user_restriction,
    enforce_listing_view_access,
    enforce_publish_access,
    is_admin,
)
from ..dependencies import current_user, optional_user, require_role

router = APIRouter(prefix="/listings", tags=["listings"])


async def listing_hidden_by_moderation(listing_id: UUID, owner_user_id: UUID, session: AsyncSession) -> bool:
    return bool(
        await active_listing_restriction(listing_id, session)
        or await active_user_restriction(owner_user_id, session)
    )


@router.get("/catalog-version", response_model=CatalogVersionResponse)
async def catalog_version(session: AsyncSession = Depends(get_session)):
    state = await session.get(CatalogState, 1)
    if not state:
        state = CatalogState(id=1, version=1, updated_at=datetime.now(UTC))
        session.add(state)
        await session.commit()
    return CatalogVersionResponse(version=str(state.version), updatedAt=state.updated_at)


@router.get("", response_model=list[ListingResponse])
async def list_listings(
    city: str | None = None,
    area: str | None = None,
    rental_mode: str | None = Query(default=None, alias="rentalMode"),
    min_price: int | None = Query(default=None, ge=0, alias="minPrice"),
    max_price: int | None = Query(default=None, ge=0, alias="maxPrice"),
    user: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_session),
):
    await enforce_listing_view_access(user, session)
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
async def search_listings(
    payload: ListingSearchRequest,
    user: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_session),
):
    await enforce_listing_view_access(user, session)
    return await search_public(session, payload)


@router.get("/mine", response_model=list[OwnedListingResponse])
async def list_my_listings(
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=10_000),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    query = owned_query().where(Listing.deleted_at.is_(None))
    if not await is_admin(user, session):
        query = query.where(Listing.owner_user_id == user.id)
    rows = (
        await session.execute(
            query.order_by(Listing.created_at.desc(), Listing.id.desc()).limit(limit).offset(offset)
        )
    ).all()
    return [owned_response_from(row) for row in rows]


@router.get("/{listing_id}", response_model=ListingResponse)
async def get_listing(
    listing_id: UUID,
    request: Request,
    response: Response,
    visitor_token: str | None = Cookie(default=None, alias="listing_visitor"),
    user: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_session),
):
    await enforce_listing_view_access(user, session)
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
                samesite="lax",
                max_age=90 * 24 * 60 * 60,
                path="/api/v1/listings",
            )
        viewer_key = anonymous_viewer_key(client_ip(request))
    if await register_view(row[0], viewer_key, session):
        row = (await session.execute(visible_query().where(Listing.id == listing_id))).one()
    return response_from(row)


@router.post("", response_model=OwnedListingResponse, status_code=status.HTTP_201_CREATED)
async def create_listing(
    payload: ListingWrite,
    user: User = Depends(require_role("host", "admin")),
    session: AsyncSession = Depends(get_session),
):
    await enforce_publish_access(user, session)
    if not user.email_verified:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "code": "EMAIL_VERIFICATION_REQUIRED",
                "message": "Confirm your email with a six-digit code before publishing a listing.",
                "fieldErrors": {},
            },
        )
    await enforce_listing_creation_limits(user, session)
    return await create_listing_service(payload, user, session)


@router.patch("/{listing_id}", response_model=OwnedListingResponse)
async def update_listing(
    listing_id: UUID,
    payload: ListingPatch,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    if payload.status in {"pending", "published"}:
        await enforce_publish_access(user, session)
    return await update_listing_service(listing_id, payload, user, session)


@router.post("/{listing_id}/renew", response_model=OwnedListingResponse)
async def renew_listing(
    listing_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await enforce_publish_access(user, session)
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
    if not listing or listing.deleted_at is not None:
        raise HTTPException(404, "Listing not found")
    owner = await session.get(User, listing.owner_user_id)
    admin = bool(user and await is_admin(user, session))
    owner_or_admin = bool(user and (listing.owner_user_id == user.id or admin))
    # A view restriction blocks public browsing, but it must not prevent a host
    # from editing media on their own listing, because that account may still be
    # explicitly allowed to publish.
    if not owner_or_admin:
        await enforce_listing_view_access(user, session)
    moderated = await listing_hidden_by_moderation(listing.id, listing.owner_user_id, session)
    public_visible = bool(
        listing.status == "published"
        and (listing.expires_at is None or listing.expires_at > datetime.now(UTC))
        and owner
        and owner.deleted_at is None
        and not owner.blocked
        and not moderated
    )
    if not owner_or_admin and not public_visible:
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
