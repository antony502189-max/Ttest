"""SQL compiler of the shared typed plan; no current-source/eligibility claim."""

from decimal import Decimal

from sqlalchemy import Numeric, and_, case, cast, func, literal, or_, select
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TEXT
from sqlalchemy.sql.elements import ColumnElement

from ..services.ai_hard_matching import FeatureRule, HardMatchPlan

_VALUE_FIELDS = {
    "policy": ("kind", "allowed"), "boolean": ("kind", "value"),
    "quantity": ("kind", "value", "unit"), "money": ("kind", "amount", "currency", "period"),
    "category": ("kind", "value", "catalog_code"),
    "geography": ("kind", "province_code", "municipality_code", "zone_id"),
    "date_range": ("kind", "start", "end"),
}


def hard_match_predicate(features: ColumnElement, plan: HardMatchPlan) -> ColumnElement[bool]:
    """Apply to current validated projections BEFORE count/order/seek/limit.

    Explicit bindings only; neither model text nor client SQL enters this tree.
    Arbitrary stored JSON still needs authoritative validation/current-source
    guards. This compiler does not establish provenance or a public query path.
    """
    array = case((func.jsonb_typeof(features) == "array", features), else_=literal([], type_=JSONB))
    element = func.jsonb_array_elements(array).table_valued("value", joins_implicitly=True).alias()
    item = cast(element.c.value, JSONB)
    qualifiers = cast(func.jsonb_strip_nulls(case((func.jsonb_typeof(item["qualifiers"]) == "object",
                                                item["qualifiers"]), else_=literal({}, type_=JSONB))), JSONB)
    value = cast(func.jsonb_strip_nulls(case((func.jsonb_typeof(item["typed_value"]) == "object",
                                           item["typed_value"]), else_=literal({}, type_=JSONB))), JSONB)

    def number(field, *, money=False):
        raw = value[field]
        pattern = r"^(0|[1-9][0-9]*)(\.[0-9]{1,2})?$" if money else r"^(0|[1-9][0-9]{0,9})$"
        safe = and_(func.jsonb_typeof(raw) == ("string" if money else "number"),
                    func.length(raw.astext) <= (16 if money else 10), raw.astext.op("~")(pattern))
        parsed = case((safe, cast(raw.astext, Numeric)), else_=None)
        return parsed if money else case((parsed <= 2_147_483_647, parsed), else_=None)

    def one(rule: FeatureRule):
        scope_conditions = []
        for key, choices in rule.scopes:
            scope_conditions.append(or_(*(
                qualifiers[key].is_(None) if option is None else qualifiers[key] == literal(option, type_=JSONB)
                for option in choices)))
        relevant = and_(item["key"].astext == rule.key, *scope_conditions)
        unique = select(func.count()).select_from(element).where(relevant).scalar_subquery() == 1
        conditions = [relevant, item["status"].astext == "explicit_allow",
                      func.jsonb_typeof(item["qualifiers"]) == "object",
                      qualifiers.op("-")(literal(list(rule.allowed_qualifiers), type_=ARRAY(TEXT))) == literal({}, type_=JSONB),
                      or_(qualifiers["approval_required"].is_(None),
                          qualifiers["approval_required"] == literal(False, type_=JSONB)),
                      func.jsonb_typeof(item["typed_value"]) == "object", value["kind"].astext == rule.kind,
                      value.op("-")(literal(list(_VALUE_FIELDS[rule.kind]), type_=ARRAY(TEXT))) == literal({}, type_=JSONB)]
        for key, choices in rule.covering_scopes:
            conditions.append(or_(*(
                qualifiers[key].is_(None) if option is None else qualifiers[key] == literal(option, type_=JSONB)
                for option in choices)))
        if rule.qualifier_min_count is not None:
            raw_count = qualifiers["max_count"]
            count = case((and_(func.jsonb_typeof(raw_count) == "number",
                              raw_count.astext.op("~")(r"^([1-9]|10)$")), cast(raw_count.astext, Numeric)), else_=None)
            conditions.append(or_(raw_count.is_(None), count >= rule.qualifier_min_count))
        for test in rule.tests:
            raw = value[test.field]
            if test.operator == "eq":
                conditions.append(raw.is_(None) if test.value is None else raw == literal(test.value, type_=JSONB))
            else:
                if test.field in {"amount", "value"}:
                    actual = number(test.field, money=test.field == "amount")
                else:
                    conditions.extend([func.jsonb_typeof(raw) == "string",
                                       raw.astext.op("~")(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"),
                                       func.pg_input_is_valid(raw.astext, "date")])
                    actual = raw.astext
                expected = Decimal(str(test.value)) if test.field == "amount" else test.value
                conditions.append(actual <= expected if test.operator == "le" else actual >= expected)
        return and_(unique, select(1).select_from(element).where(*conditions).exists())

    checks = [one(rule) for group in plan.criteria for rule in group.rules]
    return func.coalesce(and_(func.jsonb_typeof(features) == "array", func.jsonb_array_length(array) <= 128,
                             *checks), False)
