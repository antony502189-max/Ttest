"""Commercial advertising rules, independent of property listings and PSPs."""

import re
from datetime import UTC, datetime, timedelta
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

from fastapi import HTTPException

from ..models.commercial_advertisement import CommercialAdvertisement

PACKAGE_DURATION_DAYS = 30
PACKAGE_ID = "test_homepage_30d"
MAX_ACTIVE_HOMEPAGE_ADS = 12


def normalize_destination(kind: str, raw: str) -> str:
    value = raw.strip()
    if kind == "website":
        if any(char.isspace() or ord(char) < 32 or char == "\\" for char in value):
            raise ValueError("Invalid website URL")
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Only http and https website URLs are allowed")
        if parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
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
    if ad.status != "pending_review" or ad.payment_status != "paid":
        raise HTTPException(409, "Paid pending-review advertisement required")
    now = datetime.now(UTC)
    start = starts_at or ad.starts_at or now
    end = ends_at or ad.ends_at or start + timedelta(days=PACKAGE_DURATION_DAYS)
    if start.tzinfo is None or end.tzinfo is None or end <= start or end <= now:
        raise HTTPException(422, "Invalid advertisement schedule")
    ad.status = "active"
    ad.starts_at = start
    ad.ends_at = end
    ad.approved_at = now
    ad.rejected_at = None
    ad.moderation_note = None
