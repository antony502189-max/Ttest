"""Authoritative admission policy, shared by writers, public reads and maintenance.

Manual monthlyPrice is an exact EUR/month amount. Deposits and one-time fees
are separate. Fixed additional bills must be verified before publication; a
free-text bill amount is not sufficient evidence of its cadence/inclusion.
Usage-based utilities are not a fixed residential rent component.
Verified fixed charges use the explicit canonical monthly-cost contract.
"""
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy import Numeric, and_, case, cast, func, or_

MAX_MONTHLY_RENT_EUR = 1000
SUPPORTED_RENTAL_MODE = "long"
POLICY_VERSION = "long-eur-month-1000-v1"
FIXED_BILLS_PATTERN = r"^gastos mensuales obligatorios: ([0-9]+) €/mes$"
USAGE_BILLS_PATTERN = r"^(seg[uú]n consumo|gastos seg[uú]n consumo|utilities according to usage|по потреблению)$"



def exact_euro_amount(text: str) -> Decimal | None:
    """Strictly decode an advertised EUR amount without dropping thousands or cents.

    Examples: 1 200 €, 1.200 €, 1,200 €, 1.200,50 €, 1,200.50 €.
    Multiple/ambiguous prices are not exact monthly-rent evidence.
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


@dataclass(frozen=True)
class Eligibility:
    eligible: bool
    reason: str | None = None


def evaluate(*, mode, amount, currency="EUR", period="month", is_from=False,
             mandatory_monthly_fees=0, bills_included=False, bills_text=None) -> Eligibility:
    if mode != SUPPORTED_RENTAL_MODE:
        return Eligibility(False, "unsupported_rental_mode")
    if currency != "EUR":
        return Eligibility(False, "unsupported_currency")
    if period != "month":
        return Eligibility(False, "unverified_billing_period")
    if is_from is not False:
        return Eligibility(False, "uncertain_price")
    try:
        rent = Decimal(str(amount))
        fees = Decimal(str(mandatory_monthly_fees))
    except (InvalidOperation, ValueError):
        return Eligibility(False, "unverified_price")
    if not rent.is_finite() or rent <= 0 or not fees.is_finite() or fees < 0:
        return Eligibility(False, "invalid_price")
    text = (bills_text or "").strip()
    if text and not bills_included:
        fixed = re.fullmatch(FIXED_BILLS_PATTERN, text, re.IGNORECASE)
        if fixed:
            fees += Decimal(fixed.group(1))
        elif not re.fullmatch(USAGE_BILLS_PATTERN, text, re.IGNORECASE):
            return Eligibility(False, "unverified_recurring_costs")
    if rent + fees > MAX_MONTHLY_RENT_EUR:
        return Eligibility(False, "monthly_price_exceeds_limit")
    return Eligibility(True)


def listing_eligibility(listing, changes=None) -> Eligibility:
    changes = changes or {}
    external = bool(getattr(listing, "is_external", False))
    return evaluate(
        mode=changes.get("rentalMode", listing.rental_mode),
        amount=changes.get("monthlyPrice", listing.monthly_price),
        currency=getattr(listing, "source_price_currency", None) if external else "EUR",
        period=getattr(listing, "source_price_period", None) if external else "month",
        is_from=getattr(listing, "source_price_is_from", None) if external else False,
        bills_included=changes.get("billsIncluded", getattr(listing, "bills_included", False)),
        bills_text=changes.get("billsText", getattr(listing, "bills_text", None)),
    )


def require_eligible(listing, changes=None) -> None:
    result = listing_eligibility(listing, changes)
    if not result.eligible:
        raise HTTPException(422, detail={
            "code": "RENTAL_POLICY_REJECTED", "reason": result.reason,
            "message": "Only verified long-term EUR monthly rentals from 1 to 1,000 EUR are supported.",
            "fieldErrors": {"monthlyPrice": "El alquiler mensual no puede superar los 1.000 €."},
        })


def public_eligibility_clause():
    # Keep this equivalent to listing_eligibility; integration tests exercise
    # SQL and Python together, including legacy external price evidence.
    from ..models import Listing
    return and_(
        Listing.rental_mode == SUPPORTED_RENTAL_MODE,
        Listing.monthly_price > 0,
        monthly_rent_expression() <= MAX_MONTHLY_RENT_EUR,
        or_(Listing.is_external.is_(False), and_(
            Listing.source_price_currency == "EUR",
            Listing.source_price_period == "month",
            Listing.source_price_is_from.is_(False),
        )),
        or_(Listing.bills_included.is_(True), Listing.bills_text.is_(None),
            func.btrim(Listing.bills_text) == "",
            func.lower(func.btrim(Listing.bills_text)).op("~")(USAGE_BILLS_PATTERN),
            func.lower(func.btrim(Listing.bills_text)).op("~")(FIXED_BILLS_PATTERN)),
    )


def monthly_rent_expression():
    from ..models import Listing
    text = func.lower(func.btrim(Listing.bills_text))
    fee = case((Listing.bills_included.is_(True), 0),
               else_=func.coalesce(cast(func.substring(text, FIXED_BILLS_PATTERN), Numeric), 0))
    return cast(Listing.monthly_price, Numeric) + fee


def monthly_rent_total(listing):
    fixed = re.fullmatch(FIXED_BILLS_PATTERN, (getattr(listing, "bills_text", None) or "").strip(), re.IGNORECASE)
    return (listing.monthly_price or 0) + (int(fixed.group(1)) if fixed and not listing.bills_included else 0)
