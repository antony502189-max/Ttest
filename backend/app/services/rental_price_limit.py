"""Price ceiling for long-term rentals only; holiday behavior is preserved."""

import re
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy import and_, or_

MAX_LONG_TERM_RENT_EUR = 1000


def exact_euro_amount(text: str) -> Decimal | None:
    """Extract exactly one EUR amount, rejecting ambiguous or truncated prices.

    The source's legacy integer parser is not authoritative for the limit:
    '1 200 €' may otherwise be interpreted as 200, while 1000.50 loses cents.
    Both European and English grouping/decimal spellings are supported.
    """
    amounts = list(re.finditer(r"(?<![\d.,])([0-9][0-9\s.,]*?)\s*€", text))
    if len(amounts) != 1:
        return None
    number = re.sub(r"\s+", "", amounts[0].group(1))
    if re.fullmatch(r"[0-9]+", number):
        normalized = number
    elif re.fullmatch(r"[0-9]+[.,][0-9]{1,2}", number):
        normalized = number.replace(",", ".")
    elif re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]{1,2})?", number):
        normalized = number.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]{1,2})?", number):
        normalized = number.replace(",", "")
    else:
        return None
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None

def imported_price_allowed(item) -> bool:
    if item.rental_mode == "long" and getattr(item, "price_is_from", False):
        # A starting price does not guarantee that the actual monthly rent
        # is at or below the inclusive policy ceiling.
        return False
    if not long_term_price_allowed(item.rental_mode, item.price_amount):
        return False
    exact = exact_euro_amount(item.source_price_text)
    return item.rental_mode != "long" or (exact is not None and long_term_price_allowed("long", exact))


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
