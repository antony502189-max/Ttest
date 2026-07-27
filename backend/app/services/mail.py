import asyncio
import logging
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import Settings, get_settings
from ..models import MailOutbox

logger = logging.getLogger(__name__)


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


def enqueue_email_verification(session: AsyncSession, recipient: str, token: str) -> None:
    enqueue_mail(
        session,
        kind="email_verification",
        recipient=recipient,
        subject="Confirma tu correo electrónico",
        body=f"Abre este enlace para confirmar tu correo: {frontend_link(f'/verificar-email?token={token}')}",
    )


def enqueue_message_notification(session: AsyncSession, recipient: str, listing_id: str) -> None:
    enqueue_mail(
        session,
        kind="new_message",
        recipient=recipient,
        subject="Tienes un mensaje nuevo",
        body=f"Tienes un mensaje nuevo sobre un anuncio: {frontend_link(f'/habitacion/{listing_id}')}",
    )


def send_smtp(item: MailOutbox, settings: Settings) -> None:
    if not settings.smtp_host:
        raise RuntimeError("SMTP_HOST is not configured")
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = item.recipient
    message["Subject"] = item.subject
    message.set_content(item.body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


async def deliver_pending_mail(session: AsyncSession, *, limit: int | None = None) -> int:
    settings = get_settings()
    batch_size = limit or settings.mail_worker_batch_size
    items = (
        await session.scalars(
            select(MailOutbox)
            .where(MailOutbox.status == "pending", MailOutbox.attempts < settings.mail_max_attempts)
            .order_by(MailOutbox.created_at)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
    ).all()
    delivered = 0
    for item in items:
        item.attempts += 1
        try:
            if settings.smtp_host:
                await asyncio.to_thread(send_smtp, item, settings)
            elif settings.app_env == "development":
                logger.info("dev_mail", extra={"recipient": item.recipient, "kind": item.kind})
            else:
                raise RuntimeError("SMTP_HOST is required outside development")
            item.status = "sent"
            item.sent_at = datetime.now(UTC)
            item.last_error = None
            delivered += 1
        except (OSError, RuntimeError, smtplib.SMTPException) as exc:
            item.last_error = str(exc)[:2_000]
            if item.attempts >= settings.mail_max_attempts:
                item.status = "failed"
            logger.warning("mail_delivery_failed", extra={"mail_id": str(item.id), "kind": item.kind})
    await session.commit()
    return delivered
