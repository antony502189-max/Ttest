from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import decode_access_token
from ..db.session import get_session
from ..models import User

bearer = HTTPBearer(auto_error=False)


async def optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer), session: AsyncSession = Depends(get_session)
) -> User | None:
    if not credentials:
        return None
    try:
        claims = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        return None
    user = await session.scalar(select(User).where(User.id == claims.get("sub")))
    if not user or user.blocked:
        return None
    return user


async def current_user(user: User | None = Depends(optional_user)) -> User:
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    return user


def require_role(*roles: str):
    async def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
        return user

    return dependency
