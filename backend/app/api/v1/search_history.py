from fastapi import APIRouter, Depends, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...models import SearchHistory, User
from ...schemas.history import SearchHistoryRequest
from ..dependencies import current_user

router = APIRouter(prefix="/search-history", tags=["search history"])
MAX_HISTORY = 20


@router.get("", response_model=list[str])
async def list_history(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    return list(
        (await session.scalars(
            select(SearchHistory.normalized_query).where(SearchHistory.user_id == user.id).order_by(SearchHistory.searched_at.desc()).limit(MAX_HISTORY)
        )).all()
    )


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def add_history(
    payload: SearchHistoryRequest, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
):
    normalized = " ".join(payload.query.split())
    await session.execute(delete(SearchHistory).where(SearchHistory.user_id == user.id, SearchHistory.normalized_query == normalized))
    session.add(SearchHistory(user_id=user.id, normalized_query=normalized))
    overflow = (
        await session.scalars(
            select(SearchHistory.id).where(SearchHistory.user_id == user.id).order_by(SearchHistory.searched_at.desc()).offset(MAX_HISTORY)
        )
    ).all()
    if overflow:
        await session.execute(delete(SearchHistory).where(SearchHistory.id.in_(overflow)))
    await session.commit()


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_history(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await session.execute(delete(SearchHistory).where(SearchHistory.user_id == user.id))
    await session.commit()
