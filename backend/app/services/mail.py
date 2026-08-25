import asyncio
import logging
import smtplib
import ssl
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import Settings, get_settings
from ..models import MailOutbox

logger = logging.getLogger(__name__)
SENSITIVE_MAIL_KINDS = {"email_verification", "password_reset"}
REDACTED_BODY = "[redacted after successful delivery]"


class MailPayload(Protocol):
    @property
    def recipient(self) -> str: ...

    @property
    def subject(self) -> str: ...

    @property
    def body(self) -> str: ...


@dataclass(frozen=True)
class ClaimedMail:
    id: UUID
    lease_token: str
    kind: str
    recipient: str
    subject: str
    body: str
    attempts: int


def frontend_link(path: str) -> str:
    return f"{get_settings().frontend_app_url.rstrip('/')}/#{path}"


def enqueue_mail(session: AsyncSession, *, kind: str, recipient: str, subject: str, body: str) -> None:
    session.add(MailOutbox(kind=kind, recipient=recipient, subject=subject, body=body))


def enqueue_password_reset(session: AsyncSession, recipient: str, token: str) -> None:
    enqueue_mail(
        session,
        kind="password_reset",
        recipient=recipient,
        subject="Restablece tu contraseña",
        body=f"Abre este enlace para restablecer tu contraseña: {frontend_link(f'/restablecer-contrasena?token={token}')}",
    )


def enqueue_email_verification(session: AsyncSession, recipient: str, code: str) -> None:
    enqueue_mail(
        session,
        kind="email_verification",
        recipient=recipient,
        subject="Confirma tu correo electrónico",
        body=(
            f"Tu código de confirmación de 112233.es es: {code}. "
            f"Caduca en {get_settings().email_verification_minutes} minutos. No lo compartas con nadie."
        ),
    )


def send_smtp(item: MailPayload, settings: Settings) -> None:
    if not settings.smtp_host:
        raise RuntimeError("SMTP_HOST is not configured")
    message = EmailMessage()
    message["From"] = (
        formataddr((settings.smtp_from_name, settings.smtp_from))
        if settings.smtp_from_name
        else settings.smtp_from
    )
    message["To"] = item.recipient
    message["Subject"] = item.subject
    message.set_content(item.body)
    with smtplib.SMTP(
        settings.smtp_host,
        settings.smtp_port,
        timeout=settings.smtp_timeout_seconds,
    ) as smtp:
        if settings.smtp_starttls:
            smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


def retry_delay_seconds(attempts: int, settings: Settings) -> int:
    exponent = max(0, attempts - 1)
    return min(settings.mail_retry_max_seconds, settings.mail_retry_base_seconds * (2**exponent))


async def claim_pending_mail(
    session: AsyncSession,
    *,
    batch_size: int,
    settings: Settings,
) -> list[ClaimedMail]:
    """Lease a batch in one short transaction, then release all row locks."""
    now = datetime.now(UTC)
    lease_token = str(uuid4())
    items = (
        await session.scalars(
            select(MailOutbox)
            .where(
                MailOutbox.status == "pending",
                MailOutbox.attempts < settings.mail_max_attempts,
                MailOutbox.next_attempt_at <= now,
                or_(MailOutbox.lease_expires_at.is_(None), MailOutbox.lease_expires_at <= now),
            )
            .order_by(MailOutbox.next_attempt_at, MailOutbox.created_at, MailOutbox.id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
    ).all()
    lease_expires_at = now + timedelta(seconds=settings.mail_lease_seconds)
    claims: list[ClaimedMail] = []
    for item in items:
        item.attempts += 1
        item.lease_token = lease_token
        item.lease_expires_at = lease_expires_at
        claims.append(
            ClaimedMail(
                id=item.id,
                lease_token=lease_token,
                kind=item.kind,
                recipient=item.recipient,
                subject=item.subject,
                body=item.body,
                attempts=item.attempts,
            )
        )
    await session.commit()
    return claims


async def finalize_mail_claim(
    session: AsyncSession,
    claim: ClaimedMail,
    *,
    delivered: bool,
    error: str | None,
    settings: Settings,
) -> bool:
    """Finalize only the lease still owned by this worker."""
    now = datetime.now(UTC)
    values: dict[str, object] = {
        "lease_token": None,
        "lease_expires_at": None,
    }
    if delivered:
        values.update(
            status="sent",
            sent_at=now,
            last_error=None,
            body=REDACTED_BODY if claim.kind in SENSITIVE_MAIL_KINDS else claim.body,
        )
    else:
        terminal = claim.attempts >= settings.mail_max_attempts
        values.update(
            status="failed" if terminal else "pending",
            last_error=(error or "mail delivery failed")[:2_000],
            next_attempt_at=now + timedelta(seconds=retry_delay_seconds(claim.attempts, settings)),
        )
        if terminal and claim.kind in SENSITIVE_MAIL_KINDS:
            values["body"] = REDACTED_BODY

    result = await session.execute(
        update(MailOutbox)
        .where(
            MailOutbox.id == claim.id,
            MailOutbox.status == "pending",
            MailOutbox.lease_token == claim.lease_token,
        )
        .values(**values)
        .returning(MailOutbox.id)
    )
    updated_id = result.scalar_one_or_none()
    await session.commit()
    return updated_id is not None


async def deliver_pending_mail(session: AsyncSession, *, limit: int | None = None) -> int:
    settings = get_settings()
    batch_size = limit or settings.mail_worker_batch_size
    claims = await claim_pending_mail(session, batch_size=batch_size, settings=settings)
    delivered = 0

    # No database transaction or row lock is held while SMTP performs DNS,
    # TLS, authentication and network I/O. A crashed worker leaves a lease that
    # becomes claimable again after MAIL_LEASE_SECONDS.
    for claim in claims:
        error: str | None = None
        success = False
        try:
            if settings.smtp_host:
                await asyncio.to_thread(send_smtp, claim, settings)
            elif settings.app_env == "development":
                logger.info("dev_mail", extra={"recipient": claim.recipient, "kind": claim.kind})
            else:
                raise RuntimeError("SMTP_HOST is required outside development")
            success = True
        except (OSError, RuntimeError, smtplib.SMTPException) as exc:
            error = str(exc)
            logger.warning("mail_delivery_failed", extra={"mail_id": str(claim.id), "kind": claim.kind})

        if await finalize_mail_claim(
            session,
            claim,
            delivered=success,
            error=error,
            settings=settings,
        ):
            delivered += int(success)
        else:
            logger.warning("mail_lease_lost", extra={"mail_id": str(claim.id), "kind": claim.kind})
    return delivered
