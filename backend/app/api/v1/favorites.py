from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...models import DiscardedListing, Favorite, Listing, User
from ..dependencies import current_user

router = APIRouter(tags=["favorites"])


async def require_listing(listing_id: UUID, session: AsyncSession) -> None:
    if not await session.scalar(select(Listing.id).where(Listing.id == listing_id)):
        raise HTTPException(404, "Listing not found")


def collection(model, user_id: UUID):
    return select(model.listing_id).where(model.user_id == user_id).order_by(model.created_at.desc())


@router.get("/favorites", response_model=list[UUID])
async def list_favorites(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    return list((await session.scalars(collection(Favorite, user.id))).all())


@router.put("/favorites/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_favorite(listing_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await require_listing(listing_id, session)
    await session.execute(
        insert(Favorite).values(user_id=user.id, listing_id=listing_id).on_conflict_do_nothing(
            constraint="uq_favorites_user_listing"
        )
    )
    await session.commit()


@router.delete("/favorites/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(listing_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await session.execute(delete(Favorite).where(Favorite.user_id == user.id, Favorite.listing_id == listing_id))
    await session.commit()


@router.get("/discarded-listings", response_model=list[UUID])
async def list_discarded(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    return list((await session.scalars(collection(DiscardedListing, user.id))).all())


@router.delete("/discarded-listings", status_code=status.HTTP_204_NO_CONTENT)
async def clear_discarded(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await session.execute(delete(DiscardedListing).where(DiscardedListing.user_id == user.id))
    await session.commit()


@router.put("/discarded-listings/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_discarded(listing_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await require_listing(listing_id, session)
    await session.execute(
        insert(DiscardedListing).values(user_id=user.id, listing_id=listing_id).on_conflict_do_nothing(
            constraint="uq_discarded_user_listing"
        )
    )
    await session.commit()


@router.delete("/discarded-listings/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_discarded(listing_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await session.execute(delete(DiscardedListing).where(DiscardedListing.user_id == user.id, DiscardedListing.listing_id == listing_id))
    await session.commit()
