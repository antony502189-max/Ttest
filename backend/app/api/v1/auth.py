from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import get_settings
from ...core.security import create_access_token, hash_password, new_refresh_token, token_hash, verify_password
from ...db.session import get_session
from ...models import AuthSession, PasswordResetToken, User
from ...schemas.auth import (
    ForgotPasswordRequest,
    GoogleLoginRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserResponse,
)
from ..dependencies import current_user

router = APIRouter(prefix="/auth", tags=["auth"])


def public_user(user: User) -> dict:
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "phone": user.phone,
        "whatsapp": user.whatsapp,
        "telegram": user.telegram,
        "about": user.about,
        "initials": user.initials,
        "showPhone": user.show_phone,
        "showWhatsApp": user.show_whatsapp,
        "allowContactForm": user.allow_contact_form,
    }


async def issue_tokens(user: User, session: AsyncSession, response: Response) -> dict:
    raw_refresh = new_refresh_token()
    expires = datetime.now(UTC) + timedelta(days=get_settings().refresh_token_days)
    session.add(AuthSession(user_id=user.id, token_hash=token_hash(raw_refresh), expires_at=expires))
    await session.commit()
    response.set_cookie(
        "refresh_token",
        raw_refresh,
        httponly=True,
        secure=get_settings().app_env != "development",
        samesite="lax" if get_settings().app_env == "development" else "none",
        max_age=int((expires - datetime.now(UTC)).total_seconds()),
        path="/api/v1/auth",
    )
    return {"accessToken": create_access_token(str(user.id), user.role), "user": public_user(user)}


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, response: Response, session: AsyncSession = Depends(get_session)):
    email = str(payload.email).lower()
    if payload.role not in {"tenant", "host"}:
        raise HTTPException(422, "Invalid role")
    if await session.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise HTTPException(409, "Email already registered")
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        name=payload.name.strip(),
        role=payload.role,
        initials="".join(part[:1].upper() for part in payload.name.split()[:2]),
    )
    session.add(user)
    await session.flush()
    return await issue_tokens(user, session, response)


@router.post("/login")
async def login(payload: LoginRequest, response: Response, session: AsyncSession = Depends(get_session)):
    user = await session.scalar(select(User).where(func.lower(User.email) == str(payload.email).lower()))
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash) or user.blocked:
        raise HTTPException(401, "Invalid credentials")
    return await issue_tokens(user, session, response)


@router.post("/google")
async def google_login(payload: GoogleLoginRequest, response: Response, session: AsyncSession = Depends(get_session)):
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(503, "Google sign-in is not configured")
    try:
        claims = google_id_token.verify_oauth2_token(
            payload.credential, google_requests.Request(), settings.google_client_id
        )
    except ValueError:
        raise HTTPException(401, "Invalid Google credential")
    subject = claims.get("sub")
    email = str(claims.get("email", "")).lower()
    if not subject or not email or not claims.get("email_verified"):
        raise HTTPException(401, "Google account email is not verified")
    user = await session.scalar(select(User).where(User.google_subject == subject))
    if not user:
        user = await session.scalar(select(User).where(func.lower(User.email) == email))
        if user:
            user.google_subject = subject
            user.email_verified = True
        else:
            name = str(claims.get("name") or email.split("@", 1)[0]).strip()[:120]
            user = User(
                email=email, google_subject=subject, name=name, role="tenant", password_hash=None,
                initials="".join(part[:1].upper() for part in name.split()[:2]), email_verified=True,
            )
            session.add(user)
    if user.blocked:
        raise HTTPException(403, "Account is blocked")
    await session.flush()
    return await issue_tokens(user, session, response)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(payload: ForgotPasswordRequest, session: AsyncSession = Depends(get_session)):
    """Creates an expiring single-use token without exposing account existence."""
    user = await session.scalar(select(User).where(func.lower(User.email) == str(payload.email).lower()))
    response: dict[str, str] = {"message": "If the account exists, password reset instructions have been sent."}
    if not user or user.blocked:
        return response
    now = datetime.now(UTC)
    await session.execute(
        update(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id, PasswordResetToken.consumed_at.is_(None)
        ).values(consumed_at=now)
    )
    raw_token = new_refresh_token()
    session.add(PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash(raw_token),
        expires_at=now + timedelta(minutes=get_settings().password_reset_minutes),
    ))
    await session.commit()
    # A mail provider is environment-specific.  Development exposes the token
    # so the complete browser flow remains testable without an SMTP service.
    if get_settings().app_env == "development":
        response["resetToken"] = raw_token
    return response


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(payload: ResetPasswordRequest, session: AsyncSession = Depends(get_session)):
    now = datetime.now(UTC)
    reset = await session.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash(payload.token),
            PasswordResetToken.consumed_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
    )
    if not reset:
        raise HTTPException(400, "The password reset link is invalid or has expired")
    user = await session.get(User, reset.user_id)
    if not user or user.blocked:
        raise HTTPException(400, "The password reset link is invalid or has expired")
    user.password_hash = hash_password(payload.password)
    reset.consumed_at = now
    await session.execute(
        update(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)).values(revoked_at=now)
    )
    await session.commit()


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(current_user)):
    return public_user(user)


@router.post("/refresh")
async def refresh(
    response: Response, refresh_token: str | None = Cookie(default=None), session: AsyncSession = Depends(get_session)
):
    if not refresh_token:
        raise HTTPException(401, "Refresh token required")
    auth = await session.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == token_hash(refresh_token),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(UTC),
        )
    )
    if not auth:
        raise HTTPException(401, "Invalid refresh token")
    auth.revoked_at = datetime.now(UTC)
    user = await session.get(User, auth.user_id)
    if not user or user.blocked:
        await session.commit()
        raise HTTPException(401, "Authentication required")
    return await issue_tokens(user, session, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response, refresh_token: str | None = Cookie(default=None), session: AsyncSession = Depends(get_session)
):
    if refresh_token:
        auth = await session.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == token_hash(refresh_token), AuthSession.revoked_at.is_(None)
            )
        )
        if auth:
            auth.revoked_at = datetime.now(UTC)
            await session.commit()
    response.delete_cookie("refresh_token", path="/api/v1/auth")
