"""Unconnected SQL predicate for a small verified-value subset.

Caller must supply a current, authority-validated projection and combine this
predicate with existing eligibility BEFORE count/order/seek/limit. This expression
does not establish provenance, freshness, visibility or complete intent coverage.
"""

from sqlalchemy import Numeric, and_, case, cast, func, literal, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql.elements import ColumnElement

from ..schemas.ai_hard_facts import HardValueRequirements


def hard_value_predicate(features: ColumnElement, requirements: HardValueRequirements) -> ColumnElement[bool]:
    requirements = HardValueRequirements.model_validate(requirements)
    # CASE protects array expansion even for SQL NULL, JSON null or corrupt JSON.
    array = case((func.jsonb_typeof(features) == "array", features), else_=literal([], type_=JSONB))
    element = func.jsonb_array_elements(array).table_valued("value", joins_implicitly=True).alias()
    item = cast(element.c.value, JSONB)
    conditions = [func.jsonb_array_length(array) <= 128]

    def one_verified(key: str, qualifiers: dict, value_condition: ColumnElement[bool]) -> ColumnElement[bool]:
        relevant = item["key"].astext == key
        # A malformed duplicate, differently scoped or unresolved peer must never
        # be bypassed by selecting one convenient explicit value.
        unique = select(func.count()).select_from(element).where(relevant).scalar_subquery() == 1
        valid = and_(
            relevant,
            item["status"].astext == "explicit_allow",
            func.jsonb_strip_nulls(item["qualifiers"]) == literal(qualifiers, type_=JSONB),
            value_condition,
        )
        return and_(unique, select(1).select_from(element).where(valid).exists())

    if requirements.capacity_at_least is not None:
        value = item["typed_value"]
        number = value["value"].astext
        # Cast only a bounded positive integer JSON number. Planner reordering
        # cannot cast malformed strings, booleans, fractions or huge exponents.
        amount = case((and_(func.jsonb_typeof(value["value"]) == "number",
                                  number.op("~")(r"^[1-9][0-9]{0,9}$")), cast(number, Numeric)), else_=None)
        conditions.append(one_verified("capacity_total", {"inventory_scope": "rented_unit"}, and_(
            value["kind"].astext == "quantity", value["unit"].astext == "persons",
            amount <= 2_147_483_647, amount >= requirements.capacity_at_least,
        )))
    for requirement in requirements.booleans:
        conditions.append(one_verified(requirement.key, {}, item["typed_value"] == literal(
            {"kind": "boolean", "value": requirement.value}, type_=JSONB,
        )))
    return func.coalesce(and_(*conditions), False)
