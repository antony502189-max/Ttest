"""Keep verified economic criteria consistent with actual current card values.

Never use legacy boolean/capacity defaults as evidence. Price/mode displayed by
existing cards must also respect corresponding hard requirements, without unit
conversion. Missing price is not a verified budget match.
"""
from decimal import Decimal

from sqlalchemy import and_, func, or_, select, true
from sqlalchemy.sql.elements import ColumnElement

from ..models import Listing, User
from ..schemas.ai_search_intent import SearchIntent


def source_owner_eligible():
    # Minimal offline fixture anchors may have no owner. Real listings have a
    # non-null FK and still pass the existing stricter public visible_query.
    owner = select(1).where(User.id == Listing.owner_user_id, User.deleted_at.is_(None),
        User.blocked.is_(False)).correlate_except(User).exists()
    return or_(Listing.owner_user_id.is_(None), owner)


def current_card_values_predicate(intent: SearchIntent, *, columns=None):
    columns = Listing.__table__.c if columns is None else columns
    criteria = intent.criteria
    conditions: list[ColumnElement[bool]] = [true()]
    if criteria.rental_mode and criteria.rental_mode.strength == "hard":
        conditions.append(columns.rental_mode == criteria.rental_mode.value)
    if criteria.budget and criteria.budget.strength == "hard":
        budget = criteria.budget.value
        price = {"monthly": columns.monthly_price, "nightly": columns.nightly_price,
                 "weekly": columns.weekly_price}[budget.period]
        conditions.extend((price.is_not(None), price >= 0, price <= Decimal(budget.amount),
            columns.source_price_is_from.is_not(True), or_(columns.source_price_currency.is_(None),
                func.upper(func.trim(columns.source_price_currency)).in_(["EUR", "\u20ac"]))))
    return and_(*conditions)
