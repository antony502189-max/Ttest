from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...models import User
from ...schemas.history import SearchHistoryRequest
from ...services.search_state import add_history, clear_history, list_history
from ..dependencies import current_user

router = APIRouter(prefix="/search-history", tags=["search history"])


@router.get("", response_model=list[str])
async def list_history_route(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return await list_history(user, session)


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def add_history_route(
    payload: SearchHistoryRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await add_history(payload.query, user, session)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_history_route(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await clear_history(user, session)
