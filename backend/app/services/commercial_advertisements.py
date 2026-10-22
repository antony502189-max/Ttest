"""Commercial advertising rules, independent of property listings and PSPs."""

import re
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import MediaAsset
from ..models.commercial_advertisement import CommercialAdvertisement

PACKAGE_DURATION_DAYS = 1
PACKAGE_ID = "homepage_1d"
PACKAGE_PRICE_CENTS = 3000
MAX_ACTIVE_HOMEPAGE_ADS = 7


async def assert_advertisement_image_is_unique(
    session: AsyncSession,
    asset: MediaAsset,
    *,
    exclude_id: UUID | None = None,
) -> None:
    """Check the indexed, server-generated photo mark under the capacity lock.

    Upload normalization strips filenames/metadata before computing SHA-256.
    Compare content rather than asset IDs, owner IDs, title or destination.
    The 64-bit average hash alone is too ambiguous for single-image banners.
    """
    ad = CommercialAdvertisement
    query = (
        select(ad.id)
        .join(MediaAsset, MediaAsset.id == ad.image_asset_id)
        .where(
            MediaAsset.deleted_at.is_(None),
            MediaAsset.checksum == asset.checksum,
            ad.status.in_(["pending_payment", "pending_review", "active", "rejected"]),
            or_(ad.ends_at.is_(None), ad.ends_at > func.now()),
        )
        .limit(1)
    )
    if exclude_id is not None:
        query = query.where(ad.id != exclude_id)
    if await session.scalar(query) is not None:
        raise HTTPException(409, detail={
            "code": "DUPLICATE_ADVERTISEMENT_IMAGE",
            "message": "Ya existe un banner con esta imagen. Edita el anuncio existente.",
            "fieldErrors": {"imageAssetId": "Esta imagen ya pertenece a un banner existente."},
        })


async def lock_advertising_capacity(session) -> None:
    from sqlalchemy import text

    await session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
                          {"lock_key": "commercial-advertising:homepage-bottom"})


async def occupied_slots(session, *, exclude_id=None) -> int:
    """Paid review queues and provider-confirmed pending payments reserve space.

    Never release a payment on a local timer: a delayed webhook may represent a
    completed payment. The worker releases it only after Stripe confirms expiry.
    """
    from sqlalchemy import and_, func, or_, select

    from ..models.payment_order import PaymentOrder

    ad = CommercialAdvertisement
    pending_payment = select(PaymentOrder.id).where(
        PaymentOrder.kind == "advertisement", PaymentOrder.target_id == ad.id,
        PaymentOrder.status.in_(["creating", "pending"]),
    ).exists()
    query = select(func.count(ad.id)).where(ad.placement == "homepage_bottom", or_(
        and_(ad.status == "active", ad.payment_status.in_(["paid", "waived"]),
             or_(ad.ends_at.is_(None), ad.ends_at > func.now())),
        and_(ad.status.in_(["pending_review", "rejected"]), ad.payment_status.in_(["paid", "waived"]),
             or_(ad.ends_at.is_(None), ad.ends_at > func.now())),
        pending_payment,
    ))
    if exclude_id is not None:
        query = query.where(ad.id != exclude_id)
    return int(await session.scalar(query) or 0)


async def require_free_slot(session, *, exclude_id=None) -> None:
    if await occupied_slots(session, exclude_id=exclude_id) >= MAX_ACTIVE_HOMEPAGE_ADS:
        raise HTTPException(409, "No advertising slots available")


async def notify_advertiser(session, ad, kind: str, title: str, body: str) -> None:
    from ..models import User
    from .notifications import create_notification
    recipient = await session.get(User, ad.owner_user_id)
    if recipient and recipient.deleted_at is None:
        event = ad.submitted_at or ad.created_at
        await create_notification(session, recipient=recipient, kind=kind, title=title, body=body,
                                  idempotency_key=f"advertisement:{ad.id}:{kind}:{event.isoformat()}")


def normalize_destination(kind: str, raw: str) -> str:
    value = raw.strip()
    if kind == "website":
        if any(char.isspace() or ord(char) < 32 or char == "\\" for char in value):
            raise ValueError("Invalid website URL")
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Only http and https website URLs are allowed")
        hostname = parsed.hostname.rstrip(".").casefold()
        if hostname == "localhost" or hostname.endswith(".localhost"):
            raise ValueError("A public website URL is required")
        try:
            literal_ip = ip_address(hostname)
        except ValueError:
            literal_ip = None
        if literal_ip is not None and not literal_ip.is_global:
            raise ValueError("A public website URL is required")
        try:
            _ = parsed.port
        except ValueError as exc:
            raise ValueError("Invalid website port") from exc
        return urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path, parsed.query, ""))
    if kind in {"phone", "whatsapp"}:
        if not re.fullmatch(r"(?:\+|00)?[0-9][0-9 ()-]{5,23}", value):
            raise ValueError("Invalid phone number")
        digits = re.sub(r"\D", "", value)
        if value.startswith("00"):
            normalized = f"+{digits[2:]}"
        elif value.startswith("+"):
            normalized = f"+{digits}"
        elif len(digits) == 9 and digits[0] in {"6", "7", "8", "9"}:
            normalized = f"+34{digits}"
        else:
            raise ValueError("Use +country code, or a 9-digit Spanish phone number")
        international_digits = re.sub(r"\D", "", normalized)
        if not 8 <= len(international_digits) <= 15:
            raise ValueError("Invalid phone number")
        return normalized
    if kind == "email":
        if len(value) > 320 or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", value):
            raise ValueError("Invalid email address")
        return value.lower()
    raise ValueError("Invalid destination type")


def destination_url(kind: str, value: str) -> str:
    if kind == "website":
        return value
    if kind == "whatsapp":
        return f"https://wa.me/{value.lstrip('+')}"
    if kind == "phone":
        return f"tel:{value}"
    return f"mailto:{value}"


class AdvertisementPaymentService(Protocol):
    def checkout(self, ad: CommercialAdvertisement) -> str: ...
    def complete(self, ad: CommercialAdvertisement) -> None: ...


class FakeAdvertisementPaymentService:
    def checkout(self, ad: CommercialAdvertisement) -> str:
        if ad.status != "pending_payment" or ad.payment_status != "unpaid":
            raise HTTPException(409, "Advertisement is not awaiting payment")
        return "Pago de prueba — sin cargo"

    def complete(self, ad: CommercialAdvertisement) -> None:
        self.checkout(ad)
        ad.payment_status = "paid"
        ad.status = "pending_review"
        ad.submitted_at = datetime.now(UTC)


payment_service: AdvertisementPaymentService = FakeAdvertisementPaymentService()


def approve(ad: CommercialAdvertisement, starts_at: datetime | None, ends_at: datetime | None) -> None:
    if ad.status != "pending_review" or ad.payment_status not in {"paid", "waived"}:
        raise HTTPException(409, "Paid or complimentary pending-review advertisement required")
    now = datetime.now(UTC)
    start = starts_at or ad.starts_at or now
    duration = getattr(ad, "duration_days", None) or (30 if ad.package_id == "test_homepage_30d" else PACKAGE_DURATION_DAYS)
    end = ends_at or ad.ends_at or start + timedelta(days=duration)
    if start.tzinfo is None or end.tzinfo is None or end <= start or end <= now:
        raise HTTPException(422, "Invalid advertisement schedule")
    ad.status = "active"
    ad.starts_at = start
    ad.ends_at = end
    ad.approved_at = now
    ad.rejected_at = None
    ad.moderation_note = None
