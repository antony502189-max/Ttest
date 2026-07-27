from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...models import User
from ...schemas.searches import GuestStateImport
from ...services.search_state import (
    DISCARDED,
    FAVORITES,
    add_collection_item,
    clear_collection,
    import_guest_state,
    list_collection,
    remove_collection_item,
)
from ..dependencies import current_user

router = APIRouter(tags=["favorites"])


@router.get("/favorites", response_model=list[UUID])
async def list_favorites(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    return await list_collection(FAVORITES, user, session)


@router.put("/favorites/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_favorite(
    listing_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await add_collection_item(FAVORITES, "uq_favorites_user_listing", listing_id, user, session)


@router.delete("/favorites/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    listing_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await remove_collection_item(FAVORITES, listing_id, user, session)


@router.post("/account/import-guest-state", status_code=status.HTTP_204_NO_CONTENT)
async def import_guest_state_route(
    payload: GuestStateImport,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await import_guest_state(payload, user, session)


@router.get("/discarded-listings", response_model=list[UUID])
async def list_discarded(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    return await list_collection(DISCARDED, user, session)


@router.delete("/discarded-listings", status_code=status.HTTP_204_NO_CONTENT)
async def clear_discarded(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await clear_collection(DISCARDED, user, session)


@router.put("/discarded-listings/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_discarded(
    listing_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await add_collection_item(DISCARDED, "uq_discarded_user_listing", listing_id, user, session)


@router.delete("/discarded-listings/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_discarded(
    listing_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await remove_collection_item(DISCARDED, listing_id, user, session)
