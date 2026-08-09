from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import decode_access_token
from ..db.session import get_session
from ..models import User
from ..services.moderation import enforce_full_access, is_admin

bearer = HTTPBearer(auto_error=False)


async def token_user(
    credentials: HTTPAuthorizationCredentials | None,
    session: AsyncSession,
) -> User | None:
    """Resolve an access token without applying temporary moderation policy.

    This low-level resolver exists so the few identity/support endpoints that
    must explain a full restriction can still identify the account. Normal
    protected and authenticated-public application requests add policy below.
    """
    if not credentials:
        return None
    try:
        claims = decode_access_token(credentials.credentials)
        user_id = UUID(claims["sub"])
    except (InvalidTokenError, ValueError, TypeError, KeyError):
        return None
    user = await session.scalar(select(User).where(User.id == user_id))
    if not user or user.blocked or user.deleted_at is not None:
        return None
    return user


async def optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: AsyncSession = Depends(get_session),
) -> User | None:
    """Optional identity for public routes, with full-ban policy when signed in."""
    user = await token_user(credentials, session)
    if user:
        await enforce_full_access(user, session)
    return user


async def authenticated_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Low-level authenticated account, even while a moderation restriction is active.

    Keep this dependency limited to identity/moderation-support paths and admin
    authorization. Ordinary protected routes must use `current_user`.
    """
    user = await token_user(credentials, session)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    return user


async def current_user(
    user: User = Depends(authenticated_user),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Default protected-account dependency; full moderation restrictions deny normal app actions."""
    await enforce_full_access(user, session)
    return user


def require_role(*roles: str):
    async def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
        return user

    return dependency


async def require_admin(
    user: User = Depends(authenticated_user),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Admin authorization is a server-side Google-email allowlist, not a frontend role check."""
    if not await is_admin(user, session):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
    return user
