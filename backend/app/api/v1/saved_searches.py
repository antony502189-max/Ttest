from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...models import User
from ...schemas.searches import SavedSearchPatch, SavedSearchResponse, SavedSearchWrite
from ...services.search_state import (
    create_saved_search,
    delete_saved_search,
    list_saved_searches,
    update_saved_search,
)
from ..dependencies import current_user

router = APIRouter(prefix="/saved-searches", tags=["saved searches"])


@router.get("", response_model=list[SavedSearchResponse])
async def list_saved_searches_route(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return await list_saved_searches(user, session)


@router.post("", response_model=SavedSearchResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_search_route(
    payload: SavedSearchWrite,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return await create_saved_search(payload, user, session)


@router.patch("/{search_id}", response_model=SavedSearchResponse)
async def update_saved_search_route(
    search_id: UUID,
    payload: SavedSearchPatch,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return await update_saved_search(search_id, payload, user, session)


@router.delete("/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_search_route(
    search_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await delete_saved_search(search_id, user, session)
