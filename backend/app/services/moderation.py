from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User
from ..models.moderation import AdminAccess, ListingRestriction, ModerationNotice, UserRestriction
from .mail import enqueue_mail

SUPPORT_EMAIL = "tf.shuler@gmail.com"
RESTRICTION_TYPES = {"full", "publish", "view_listings"}


def normalize_email(email: str) -> str:
    return email.strip().lower()


def active_window(model):
    now = func.now()
    return (
        model.revoked_at.is_(None),
        model.starts_at <= now,
        or_(model.ends_at.is_(None), model.ends_at > now),
    )


async def is_admin(user: User, session: AsyncSession) -> bool:
    if getattr(user, "role", None) == "admin":
        return True
    if not getattr(user, "google_subject", None):
        return False
    email = normalize_email(user.email)
    row = await session.get(AdminAccess, email)
    return bool(row and row.active)


async def active_user_restriction(user_id: UUID, session: AsyncSession) -> UserRestriction | None:
    # Application writes serialize restrictions per user, so normally only one
    # active row exists. Keep deterministic precedence as a defensive fallback
    # for manually repaired/imported data or a historical race: full access
    # denial must never be shadowed by a narrower restriction. Within the same
    # type, a permanent restriction takes precedence over a dated one.
    priority = case(
        (UserRestriction.restriction_type == "full", 0),
        (UserRestriction.restriction_type == "publish", 1),
        else_=2,
    )
    return await session.scalar(
        select(UserRestriction)
        .where(UserRestriction.user_id == user_id, *active_window(UserRestriction))
        .order_by(
            priority,
            UserRestriction.ends_at.asc().nullsfirst(),
            UserRestriction.starts_at.desc(),
        )
        .limit(1)
    )


async def active_listing_restriction(listing_id: UUID, session: AsyncSession) -> ListingRestriction | None:
    return await session.scalar(
        select(ListingRestriction)
        .where(ListingRestriction.listing_id == listing_id, *active_window(ListingRestriction))
        .order_by(ListingRestriction.ends_at.desc(), ListingRestriction.starts_at.desc())
        .limit(1)
    )


def restriction_error(restriction: UserRestriction, *, code: str) -> HTTPException:
    return HTTPException(
        status.HTTP_403_FORBIDDEN,
        detail={
            "code": code,
            "message": restriction.reason,
            "fieldErrors": {},
            "restriction": {
                "type": restriction.restriction_type,
                "reason": restriction.reason,
                "until": restriction.ends_at.isoformat() if restriction.ends_at else None,
                "supportEmail": SUPPORT_EMAIL,
            },
        },
    )


async def enforce_full_access(user: User, session: AsyncSession) -> None:
    restriction = await active_user_restriction(user.id, session)
    if restriction and restriction.restriction_type == "full":
        raise restriction_error(restriction, code="ACCOUNT_RESTRICTED")


async def enforce_publish_access(user: User, session: AsyncSession) -> None:
    restriction = await active_user_restriction(user.id, session)
    if restriction and restriction.restriction_type in {"full", "publish"}:
        raise restriction_error(restriction, code="PUBLISHING_RESTRICTED")


async def enforce_listing_view_access(user: User | None, session: AsyncSession) -> None:
    if not user:
        return
    restriction = await active_user_restriction(user.id, session)
    if restriction and restriction.restriction_type in {"full", "view_listings"}:
        raise restriction_error(restriction, code="LISTING_ACCESS_RESTRICTED")


def add_notice(session: AsyncSession, user_id: UUID, *, kind: str, title: str, body: str) -> None:
    session.add(ModerationNotice(user_id=user_id, kind=kind, title=title, body=body))


def restriction_period_text(until: datetime | None) -> str:
    if until is None:
        return "de forma indefinida"
    return f"hasta {until.astimezone(UTC).strftime('%Y-%m-%d %H:%M UTC')}"


def enqueue_restriction_email(
    session: AsyncSession,
    recipient: str,
    *,
    restriction_type: str,
    reason: str,
    until: datetime | None,
) -> None:
    labels = {
        "full": "restricción completa de la cuenta",
        "publish": "restricción para publicar anuncios",
        "view_listings": "restricción para acceder a anuncios",
    }
    label = labels.get(restriction_type, "restricción de la cuenta")
    enqueue_mail(
        session,
        kind="moderation_restriction",
        recipient=recipient,
        subject="Se ha aplicado una restricción a tu cuenta",
        body=(
            f"Se ha aplicado una {label} {restriction_period_text(until)}.\n\n"
            f"Motivo: {reason}\n\n"
            f"Si crees que se trata de un error, escribe a {SUPPORT_EMAIL}."
        ),
    )


def enqueue_unrestriction_email(session: AsyncSession, recipient: str) -> None:
    enqueue_mail(
        session,
        kind="moderation_unrestricted",
        recipient=recipient,
        subject="Se ha retirado la restricción de tu cuenta",
        body=f"La restricción de tu cuenta se ha retirado. Si necesitas ayuda, escribe a {SUPPORT_EMAIL}.",
    )


def enqueue_listing_restriction_email(
    session: AsyncSession,
    recipient: str,
    *,
    listing_title: str,
    reason: str,
    until: datetime,
) -> None:
    enqueue_mail(
        session,
        kind="listing_restriction",
        recipient=recipient,
        subject="Tu anuncio ha sido restringido",
        body=(
            f"El anuncio «{listing_title}» se ha ocultado hasta {until.astimezone(UTC).strftime('%Y-%m-%d %H:%M UTC')}.\n\n"
            f"Motivo: {reason}\n\n"
            f"Si crees que se trata de un error, escribe a {SUPPORT_EMAIL}."
        ),
    )


def enqueue_listing_unrestriction_email(session: AsyncSession, recipient: str, *, listing_title: str) -> None:
    enqueue_mail(
        session,
        kind="listing_unrestricted",
        recipient=recipient,
        subject="Se ha retirado la restricción de tu anuncio",
        body=f"La restricción del anuncio «{listing_title}» se ha retirado. Si necesitas ayuda, escribe a {SUPPORT_EMAIL}.",
    )
