from datetime import UTC, datetime

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import get_settings
from ...db.session import get_session
from ...models import User
from ...schemas.auth import (
    ForgotPasswordRequest,
    GoogleLoginRequest,
    GoogleRoleRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserResponse,
    VerifyEmailRequest,
)
from ...services.auth import (
    AuthResult,
    google_login_user,
    login_user,
    public_user,
    refresh_user_session,
    register_user,
    request_password_reset,
    request_verification,
    reset_user_password,
    revoke_session,
    verify_user_email,
)
from ..dependencies import current_user

router = APIRouter(prefix="/auth", tags=["auth"])


def require_cookie_origin(request: Request) -> None:
    """Reject cross-site cookie issuance/mutation outside local development and tests."""
    settings = get_settings()
    origin = request.headers.get("origin")
    if settings.app_env.lower() not in {"development", "test"} and origin not in settings.origins:
        raise HTTPException(403, "Invalid request origin")


def request_metadata(request: Request) -> tuple[str, str]:
    return request.headers.get("user-agent", ""), request.client.host if request.client else "unknown"


def set_refresh_cookie(response: Response, result: AuthResult) -> dict:
    settings = get_settings()
    response.set_cookie(
        "refresh_token",
        result.refresh_token,
        httponly=True,
        secure=settings.is_production,
        samesite="none" if settings.is_production else "lax",
        max_age=max(1, int((result.refresh_expires_at - datetime.now(UTC)).total_seconds())),
        path="/api/v1/auth",
    )
    return {"accessToken": result.access_token, "user": public_user(result.user)}


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    response: Response,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    require_cookie_origin(request)
    user_agent, client_ip = request_metadata(request)
    result = await register_user(payload, session, user_agent=user_agent, client_ip=client_ip)
    return set_refresh_cookie(response, result)


@router.post("/login")
async def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    require_cookie_origin(request)
    user_agent, client_ip = request_metadata(request)
    result = await login_user(
        str(payload.email),
        payload.password,
        session,
        user_agent=user_agent,
        client_ip=client_ip,
    )
    return set_refresh_cookie(response, result)


@router.post("/google")
async def google_login(
    payload: GoogleLoginRequest,
    response: Response,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    require_cookie_origin(request)
    user_agent, client_ip = request_metadata(request)
    result = await google_login_user(payload, session, user_agent=user_agent, client_ip=client_ip)
    return set_refresh_cookie(response, result)


@router.post("/google/role", response_model=UserResponse)
async def select_google_role(
    payload: GoogleRoleRequest,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    require_cookie_origin(request)
    if user.role != "pending" or not user.google_subject:
        raise HTTPException(409, "Google account role is already set")
    user.role = payload.role
    await session.commit()
    await session.refresh(user)
    return public_user(user)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(payload: ForgotPasswordRequest, session: AsyncSession = Depends(get_session)):
    return await request_password_reset(str(payload.email), session)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(payload: ResetPasswordRequest, session: AsyncSession = Depends(get_session)):
    await reset_user_password(payload.token, payload.password, session)


@router.post("/request-email-verification", status_code=status.HTTP_202_ACCEPTED)
async def request_email_verification(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return await request_verification(user, session)


@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT)
async def verify_email(payload: VerifyEmailRequest, session: AsyncSession = Depends(get_session)):
    await verify_user_email(payload.token, session)


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(current_user)):
    return public_user(user)


@router.post("/refresh")
async def refresh(
    response: Response,
    request: Request,
    refresh_token: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_session),
):
    require_cookie_origin(request)
    if not refresh_token:
        raise HTTPException(401, "Refresh token required")
    user_agent, client_ip = request_metadata(request)
    result = await refresh_user_session(
        refresh_token,
        session,
        user_agent=user_agent,
        client_ip=client_ip,
    )
    return set_refresh_cookie(response, result)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    request: Request,
    refresh_token: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_session),
):
    require_cookie_origin(request)
    await revoke_session(refresh_token, session)
    response.delete_cookie("refresh_token", path="/api/v1/auth")
