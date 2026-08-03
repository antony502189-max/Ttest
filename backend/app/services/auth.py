from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..core.security import (
    create_access_token,
    hash_password_async,
    new_refresh_token,
    token_hash,
    verify_password_async,
)
from ..models import AuthSession, EmailVerificationToken, PasswordResetToken, User
from ..schemas.auth import GoogleLoginRequest, RegisterRequest
from .mail import enqueue_email_verification, enqueue_password_reset


@dataclass(frozen=True)
class AuthResult:
    access_token: str
    refresh_token: str
    refresh_expires_at: datetime
    user: User


def google_email_is_authoritative(claims: dict, email: str) -> bool:
    """Whether Google can safely prove ownership of an existing local email."""
    return email.rsplit("@", 1)[-1] == "gmail.com" or bool(claims.get("hd"))


def verify_google_credential(credential: str, client_id: str) -> dict:
    return dict(
        google_id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            client_id,
        )
    )


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
        "avatarUrl": f"/api/v1/media/{user.avatar_asset_id}" if user.avatar_asset_id else None,
    }


def masked_email(email: str) -> str:
    local, domain = email.split("@", 1)
    return f"{local[:1]}{'*' * max(1, len(local) - 1)}@{domain}"


def verification_code_hash(user_id: object, code: str) -> str:
    """Key a low-entropy OTP so a database leak cannot be brute-forced offline."""
    secret = get_settings().verification_hmac_secret.encode()
    message = f"{user_id}:{code}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


async def issue_session(
    user: User,
    session: AsyncSession,
    *,
    user_agent: str,
    client_ip: str,
    previous_session: AuthSession | None = None,
) -> AuthResult:
    raw_refresh = new_refresh_token()
    expires = datetime.now(UTC) + timedelta(days=get_settings().refresh_token_days)
    auth_session = AuthSession(
        user_id=user.id,
        token_hash=token_hash(raw_refresh),
        expires_at=expires,
        user_agent=user_agent[:512] or None,
        ip_hash=token_hash(client_ip),
    )
    session.add(auth_session)
    await session.flush()
    if previous_session:
        previous_session.revoked_at = datetime.now(UTC)
        previous_session.replaced_by = auth_session.id
    await session.commit()
    return AuthResult(
        access_token=create_access_token(str(user.id), user.role),
        refresh_token=raw_refresh,
        refresh_expires_at=expires,
        user=user,
    )


async def register_user(
    payload: RegisterRequest,
    session: AsyncSession,
    *,
    user_agent: str,
    client_ip: str,
) -> AuthResult:
    email = str(payload.email).lower()
    if payload.role not in {"tenant", "host"}:
        raise HTTPException(422, "Invalid role")
    if await session.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise HTTPException(409, "Email already registered")
    user = User(
        email=email,
        password_hash=await hash_password_async(payload.password),
        name=payload.name,
        role=payload.role,
        initials="".join(part[:1].upper() for part in payload.name.split()[:2]),
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "Email already registered") from exc
    return await issue_session(user, session, user_agent=user_agent, client_ip=client_ip)


async def login_user(
    email: str,
    password: str,
    session: AsyncSession,
    *,
    user_agent: str,
    client_ip: str,
) -> AuthResult:
    user = await session.scalar(select(User).where(func.lower(User.email) == email.lower()))
    password_valid = await verify_password_async(
        password,
        user.password_hash if user else None,
    )
    if not user or not password_valid or user.blocked or user.deleted_at:
        raise HTTPException(401, "Invalid credentials")
    return await issue_session(user, session, user_agent=user_agent, client_ip=client_ip)


async def google_login_user(
    payload: GoogleLoginRequest,
    session: AsyncSession,
    *,
    user_agent: str,
    client_ip: str,
) -> AuthResult:
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(503, "Google sign-in is not configured")
    try:
        claims = await asyncio.to_thread(
            verify_google_credential,
            payload.credential,
            settings.google_client_id,
        )
    except ValueError as exc:
        raise HTTPException(401, "Invalid Google credential") from exc
    if claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        raise HTTPException(401, "Invalid Google credential")
    subject = claims.get("sub")
    email = str(claims.get("email", "")).lower()
    if not subject or not email or claims.get("email_verified") is not True:
        raise HTTPException(401, "Google account email is not verified")
    user = await session.scalar(select(User).where(User.google_subject == subject))
    if not user:
        user = await session.scalar(select(User).where(func.lower(User.email) == email))
        if user:
            if not google_email_is_authoritative(claims, email):
                raise HTTPException(409, "Confirm the existing account before linking Google")
            user.google_subject = subject
            user.email_verified = True
        else:
            name = str(claims.get("name") or email.split("@", 1)[0]).strip()[:120]
            user = User(
                email=email,
                google_subject=subject,
                name=name,
                role="pending",
                password_hash=None,
                initials="".join(part[:1].upper() for part in name.split()[:2]),
                email_verified=True,
            )
            session.add(user)
    if user.blocked or user.deleted_at:
        raise HTTPException(403, "Account is blocked")
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        user = await session.scalar(
            select(User).where(or_(User.google_subject == subject, func.lower(User.email) == email))
        )
        if not user or user.blocked or user.deleted_at:
            raise HTTPException(409, "Google account could not be linked") from exc
        if user.google_subject is None:
            if not google_email_is_authoritative(claims, email):
                raise HTTPException(409, "Confirm the existing account before linking Google") from exc
            user.google_subject = subject
            user.email_verified = True
            try:
                await session.flush()
            except IntegrityError as retry_exc:
                await session.rollback()
                raise HTTPException(409, "Google account could not be linked") from retry_exc
    return await issue_session(user, session, user_agent=user_agent, client_ip=client_ip)


async def request_password_reset(email: str, session: AsyncSession) -> dict[str, str]:
    user = await session.scalar(select(User).where(func.lower(User.email) == email.lower()))
    response = {"message": "If the account exists, password reset instructions have been sent."}
    if not user or user.blocked or user.deleted_at:
        return response
    now = datetime.now(UTC)
    await session.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.consumed_at.is_(None))
        .values(consumed_at=now)
    )
    raw_token = new_refresh_token()
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash(raw_token),
            expires_at=now + timedelta(minutes=get_settings().password_reset_minutes),
        )
    )
    enqueue_password_reset(session, user.email, raw_token)
    await session.commit()
    if get_settings().app_env in {"development", "test"}:
        response["resetToken"] = raw_token
    return response


async def reset_user_password(raw_token: str, password: str, session: AsyncSession) -> None:
    now = datetime.now(UTC)
    reset = await session.scalar(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == token_hash(raw_token),
            PasswordResetToken.consumed_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .with_for_update()
    )
    if not reset:
        raise HTTPException(400, "The password reset link is invalid or has expired")
    user = await session.get(User, reset.user_id)
    if not user or user.blocked or user.deleted_at:
        raise HTTPException(400, "The password reset link is invalid or has expired")
    user.password_hash = await hash_password_async(password)
    reset.consumed_at = now
    await session.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await session.commit()


async def request_verification(user: User, session: AsyncSession) -> dict[str, str | int]:
    response: dict[str, str | int] = {
        "message": "If needed, a six-digit verification code has been sent.",
        "email": masked_email(user.email),
        "cooldownSeconds": 60,
    }
    if user.email_verified:
        return response
    now = datetime.now(UTC)
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"email-verification:{user.id}"},
    )
    issued_in_hour = (
        await session.scalars(
            select(EmailVerificationToken)
            .where(
                EmailVerificationToken.user_id == user.id,
                EmailVerificationToken.created_at > now - timedelta(hours=1),
            )
            .order_by(EmailVerificationToken.created_at.desc())
        )
    ).all()
    if len(issued_in_hour) >= 5:
        raise HTTPException(429, "Too many verification codes requested; try again later")
    if issued_in_hour and issued_in_hour[0].created_at > now - timedelta(seconds=60):
        raise HTTPException(429, "Wait before requesting another verification code")
    await session.execute(
        update(EmailVerificationToken)
        .where(EmailVerificationToken.user_id == user.id, EmailVerificationToken.consumed_at.is_(None))
        .values(consumed_at=now)
    )
    verification_code = f"{secrets.randbelow(1_000_000):06d}"
    session.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=verification_code_hash(user.id, verification_code),
            expires_at=now + timedelta(minutes=get_settings().email_verification_minutes),
        )
    )
    enqueue_email_verification(session, user.email, verification_code)
    await session.commit()
    if get_settings().app_env == "development":
        response["verificationCode"] = verification_code
    return response


async def verify_user_email(user: User, code: str, session: AsyncSession) -> None:
    now = datetime.now(UTC)
    verification = await session.scalar(
        select(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.consumed_at.is_(None),
        )
        .order_by(EmailVerificationToken.created_at.desc())
        .with_for_update()
    )
    if not verification or verification.expires_at <= now:
        raise HTTPException(400, "The email verification code is invalid or has expired")
    candidate_hash = verification_code_hash(user.id, code)
    if not hmac.compare_digest(verification.token_hash, candidate_hash):
        verification.attempts += 1
        if verification.attempts >= 5:
            verification.consumed_at = now
        await session.commit()
        raise HTTPException(400, "The email verification code is invalid or has expired")
    user.email_verified = True
    verification.consumed_at = now
    await session.commit()


async def refresh_user_session(
    raw_refresh: str,
    session: AsyncSession,
    *,
    user_agent: str,
    client_ip: str,
) -> AuthResult:
    now = datetime.now(UTC)
    auth = await session.scalar(
        select(AuthSession).where(AuthSession.token_hash == token_hash(raw_refresh)).with_for_update()
    )
    if not auth or auth.expires_at <= now:
        raise HTTPException(401, "Invalid refresh token")
    if auth.revoked_at is not None:
        if auth.replaced_by is not None:
            await session.execute(
                update(AuthSession)
                .where(AuthSession.user_id == auth.user_id, AuthSession.revoked_at.is_(None))
                .values(revoked_at=now)
            )
            await session.commit()
        raise HTTPException(401, "Invalid refresh token")
    user = await session.get(User, auth.user_id)
    if not user or user.blocked or user.deleted_at:
        auth.revoked_at = now
        await session.commit()
        raise HTTPException(401, "Authentication required")
    return await issue_session(
        user,
        session,
        user_agent=user_agent,
        client_ip=client_ip,
        previous_session=auth,
    )


async def revoke_session(raw_refresh: str | None, session: AsyncSession) -> None:
    if not raw_refresh:
        return
    auth = await session.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == token_hash(raw_refresh),
            AuthSession.revoked_at.is_(None),
        )
    )
    if auth:
        auth.revoked_at = datetime.now(UTC)
        await session.commit()
