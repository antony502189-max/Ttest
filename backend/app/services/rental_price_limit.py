"""Price ceiling for long-term rentals only; holiday behavior is preserved."""

import re
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy import and_, or_

MAX_LONG_TERM_RENT_EUR = 1000


def exact_euro_amount(text: str) -> Decimal | None:
    """Read the advertised amount before the legacy importer truncates cents."""
    found = re.search(r"(?:desde\s*)?([\d.]+(?:,\d{1,2})?)\s*€", text, re.IGNORECASE)
    if not found:
        return None
    number = found.group(1)
    if not ("," not in number and re.search(r"\.\d{1,2}$", number)):
        number = number.replace(".", "").replace(",", ".")
    try:
        return Decimal(number)
    except InvalidOperation:
        return None


def imported_price_allowed(item) -> bool:
    if not long_term_price_allowed(item.rental_mode, item.price_amount):
        return False
    exact = exact_euro_amount(item.source_price_text)
    return item.rental_mode != "long" or exact is None or long_term_price_allowed("long", exact)


def long_term_price_allowed(mode, amount) -> bool:
    if mode != "long":
        return True
    try:
        price = Decimal(str(amount))
    except (InvalidOperation, ValueError):
        return False
    return price.is_finite() and 0 < price <= MAX_LONG_TERM_RENT_EUR


def listing_price_allowed(listing, changes=None) -> bool:
    changes = changes or {}
    return long_term_price_allowed(
        changes.get("rentalMode", getattr(listing, "rental_mode", None)),
        changes.get("monthlyPrice", getattr(listing, "monthly_price", None)),
    )


def require_listing_price(listing, changes=None) -> None:
    if not listing_price_allowed(listing, changes):
        raise HTTPException(
            422,
            detail={
                "code": "LONG_TERM_PRICE_LIMIT",
                "message": "Long-term monthly rent must be between 1 and 1,000 EUR.",
                "fieldErrors": {"monthlyPrice": "El alquiler mensual no puede superar los 1.000 €."},
            },
        )


def public_price_limit_clause():
    from ..models import Listing

    return or_(
        Listing.rental_mode != "long",
        and_(
            Listing.monthly_price > 0,
            Listing.monthly_price <= MAX_LONG_TERM_RENT_EUR,
        ),
    )
