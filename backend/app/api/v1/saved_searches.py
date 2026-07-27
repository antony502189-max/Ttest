from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...models import SavedSearch, User
from ...schemas.searches import SavedSearchPatch, SavedSearchResponse, SavedSearchWrite
from ..dependencies import current_user

router = APIRouter(prefix="/saved-searches", tags=["saved searches"])


def public_search(search: SavedSearch) -> SavedSearchResponse:
    return SavedSearchResponse(
        id=search.id, name=search.name, query=search.query, rentalMode=search.rental_mode, filters=search.filters,
        polygon=search.polygon, alertsEnabled=search.alerts_enabled, createdAt=search.created_at, updatedAt=search.updated_at,
    )


@router.get("", response_model=list[SavedSearchResponse])
async def list_saved_searches(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    searches = (await session.scalars(select(SavedSearch).where(SavedSearch.user_id == user.id).order_by(SavedSearch.created_at.desc()))).all()
    return [public_search(search) for search in searches]


@router.post("", response_model=SavedSearchResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_search(
    payload: SavedSearchWrite, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
):
    search = SavedSearch(
        user_id=user.id, name=payload.name.strip(), query=payload.query.strip(), rental_mode=payload.rentalMode,
        filters=payload.filters, polygon=[point.model_dump() for point in payload.polygon], alerts_enabled=payload.alertsEnabled,
    )
    session.add(search)
    await session.commit()
    await session.refresh(search)
    return public_search(search)


@router.patch("/{search_id}", response_model=SavedSearchResponse)
async def update_saved_search(
    search_id: UUID, payload: SavedSearchPatch, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
):
    search = await session.scalar(select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.user_id == user.id))
    if not search:
        raise HTTPException(404, "Saved search not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key == "alertsEnabled":
            search.alerts_enabled = value
        elif key == "polygon" and value is not None:
            search.polygon = [point if isinstance(point, dict) else point.model_dump() for point in value]
        else:
            setattr(search, key, value.strip() if isinstance(value, str) else value)
    await session.commit()
    await session.refresh(search)
    return public_search(search)


@router.delete("/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_search(search_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    search = await session.scalar(select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.user_id == user.id))
    if not search:
        raise HTTPException(404, "Saved search not found")
    await session.delete(search)
    await session.commit()
