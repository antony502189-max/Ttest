"""Deterministic typed hard matching shared by SQL and offline evaluation.

No source authority/freshness assertion. The caller supplies a current validated
projection, server vocabulary and existing public eligibility before pagination.
No scoring, implicit unit conversion, policy selection or production activation.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from ..repositories.ai_search_sessions import IntentVocabulary
from ..schemas.ai_listing_facts import FactVocabulary, SearchProjection
from ..schemas.ai_search_intent import SearchIntent

Scalar = str | int | bool | None


@dataclass(frozen=True)
class ValueTest:
    field: str
    operator: Literal["eq", "le", "ge"]
    value: Scalar


@dataclass(frozen=True)
class FeatureRule:
    key: str
    # An absent qualifier is represented as None. All qualifier keys, including
    # optional bounds, must belong to allowed_qualifiers; no hidden conditions.
    scopes: tuple[tuple[str, tuple[Scalar, ...]], ...]
    allowed_qualifiers: tuple[str, ...]
    kind: str
    tests: tuple[ValueTest, ...]
    qualifier_min_count: int | None = None
    covering_scopes: tuple[tuple[str, tuple[Scalar, ...]], ...] = ()


@dataclass(frozen=True)
class CriterionRules:
    name: str
    rules: tuple[FeatureRule, ...]

    def __post_init__(self):
        if not self.rules:
            raise ValueError("empty hard criterion cannot confirm a match")


@dataclass(frozen=True)
class HardMatchPlan:
    criteria: tuple[CriterionRules, ...]


def compile_hard_match(intent: SearchIntent, vocabulary: FactVocabulary) -> HardMatchPlan:
    intent = SearchIntent.model_validate(intent.model_dump(exclude_none=True))
    vocabulary = FactVocabulary.model_validate(vocabulary)
    IntentVocabulary(vocabulary.amenity_codes, vocabulary.catalog_other_codes,
                     vocabulary.municipality_zones).validate(intent.criteria)
    groups: list[CriterionRules] = []

    def rule(key, kind, tests, *, scopes=(), allowed=(), count=None, coverage=()):
        return FeatureRule(key, tuple(scopes), tuple(allowed), kind, tuple(ValueTest(*t) for t in tests), count, tuple(coverage))

    def scalar(key, kind, field, value):
        return rule(key, kind, [(field, "eq", value)])

    def policy(key, scopes=(), allowed=()):
        return rule(key, "policy", [("allowed", "eq", True)], scopes=scopes, allowed=allowed)

    def capacity(key, size):
        return rule(key, "quantity", [("unit", "eq", "persons"), ("value", "ge", size)],
                    scopes=(("inventory_scope", ("rented_unit",)),), allowed=("inventory_scope",))

    for name in type(intent.criteria).model_fields:
        criterion = getattr(intent.criteria, name)
        if criterion is None or criterion.strength != "hard":
            continue
        value = criterion.value
        rules = []
        if name in {"furnished", "bills_included", "balcony", "terrace"}:
            rules = [scalar(name, "boolean", "value", value)]
        elif name == "rental_mode":
            rules = [scalar(name, "category", "value", value)]
        elif name == "accommodation":
            rules = [rule(name, "category", [("value", "eq", value.kind),
                                             ("catalog_code", "eq", value.catalog_code)])]
        elif name == "geography":
            tests = [(field, "eq", getattr(value, field)) for field in
                     ("province_code", "municipality_code", "zone_id") if getattr(value, field) is not None]
            rules = [rule(name, "geography", tests)]
        elif name == "budget":
            rules = [rule("price", "money", [("currency", "eq", value.currency),
                                             ("period", "eq", value.period), ("amount", "le", value.amount)])]
        elif name == "deposit":
            tests = ([("currency", "eq", value.currency), ("period", "eq", value.period),
                      ("amount", "le", value.amount)] if value.kind == "money" else
                     [("unit", "eq", value.unit), ("value", "le", value.value)])
            rules = [rule(name, value.kind, tests)]
        elif name == "party":
            total = value.adults + value.children
            # Availability is distinct from physical capacity. Requiring both
            # avoids treating occupied places as available, without consulting
            # legacy roomCapacity/currentResidents defaults.
            rules = [capacity("capacity_total", total), capacity("available_spots", total)]
            if value.children:
                rules.append(policy("children", allowed=("approval_required",)))
            if value.relationship == "couple":
                rules.append(policy("couples", allowed=("approval_required",)))
            elif value.relationship == "friends":
                # No guessed catalog mapping: a literal reviewed server code is
                # required. Missing vocabulary is an error, never dropped.
                if "friends" not in vocabulary.tenant_group_codes:
                    raise ValueError("friends tenant-group vocabulary is not configured")
                rules.append(policy("tenant_groups", scopes=(("tenant_group", ("friends",)),),
                                    allowed=("tenant_group", "approval_required")))
        elif name == "pets":
            for pet in value:
                scopes = (("species", (None, pet.species)),
                          ("size", (None, "unspecified", "small", "medium", "large") if pet.size == "unspecified" else
                           (None, "unspecified", pet.size)))
                # A generic pet limit might constrain all species together.
                # Use total requested pets even for specific scoped rules;
                # this conservative bound never overstates permission.
                rules.append(rule("pets", "policy", [("allowed", "eq", True)], scopes=scopes,
                                  allowed=("species", "size", "max_count", "approval_required"),
                                  count=sum(p.count for p in value),
                                  coverage=(("size", (None, "unspecified")),) if pet.size == "unspecified" else ()))
        elif name == "smoking":
            smoking_scopes: tuple[str, ...] = (value.scope, "outdoors") if value.scope in {"balcony", "terrace"} else (value.scope,)
            if value.scope == "outdoors":
                smoking_scopes = ("outdoors", "balcony", "terrace")
            rules = [rule(name, "policy", [("allowed", "eq", True)],
                          scopes=(("smoking_scope", smoking_scopes),),
                          allowed=("smoking_scope", "approval_required"),
                          coverage=(("smoking_scope", ("outdoors",)),) if value.scope == "outdoors" else ())]
        elif name == "amenities":
            rules = [rule("amenity", "boolean", [("value", "eq", True)],
                          scopes=(("amenity_code", (code,)),), allowed=("amenity_code",)) for code in value]
        elif name == "dates":
            rules = [rule("availability", "date_range", [("start", "le", value.check_in),
                                                         ("end", "ge", value.check_out)],
                          scopes=(("inventory_scope", ("rented_unit",)),), allowed=("inventory_scope",))]
            nights = (date.fromisoformat(value.check_out) - date.fromisoformat(value.check_in)).days
            rules.extend(rule(key, "quantity", [("unit", "eq", "nights"), ("value", op, nights)])
                         for key, op in (("minimum_stay", "le"), ("maximum_stay", "ge")))
        elif name == "stay":
            # Missing min/max is unknown, never an invented unbounded interval.
            rules = [rule(key, "quantity", [("unit", "eq", value.unit), ("value", op, value.value)])
                     for key, op in (("minimum_stay", "le"), ("maximum_stay", "ge"))]
        else:
            raise ValueError(f"unsupported hard criterion: {name}")
        groups.append(CriterionRules(name, tuple(rules)))
    return HardMatchPlan(tuple(groups))


def evaluate_hard_match(plan: HardMatchPlan, projection: SearchProjection) -> tuple[str, ...]:
    """Return unmet hard criterion names, in schema order. Empty means compatible.

    This says nothing about listing eligibility, freshness or query count. It
    must not be used as a per-card post-pagination filter.
    """
    projection = SearchProjection.model_validate(projection.model_dump())

    def matches(rule: FeatureRule) -> bool:
        candidates = [feature for feature in projection.features if feature.key == rule.key and all(
            getattr(feature.qualifiers, key) in values for key, values in rule.scopes)]
        if len(candidates) != 1:
            return False
        feature = candidates[0]
        if not all(getattr(feature.qualifiers, key) in values for key, values in rule.covering_scopes):
            return False
        qualifiers = feature.qualifiers.model_dump(exclude_none=True)
        if set(qualifiers) - set(rule.allowed_qualifiers) or qualifiers.get("approval_required") is True:
            return False
        if rule.qualifier_min_count is not None and qualifiers.get("max_count", 10) < rule.qualifier_min_count:
            return False
        value = feature.typed_value
        if feature.status != "explicit_allow" or value is None or value.kind != rule.kind:
            return False
        for test in rule.tests:
            actual = getattr(value, test.field, None)
            expected: Any = test.value
            if test.field == "amount":
                actual, expected = Decimal(str(actual)), Decimal(str(expected))
            if test.operator == "eq" and actual != expected:
                return False
            if test.operator == "le" and (actual is None or actual > expected):
                return False
            if test.operator == "ge" and (actual is None or actual < expected):
                return False
        return True

    return tuple(group.name for group in plan.criteria if not all(matches(rule) for rule in group.rules))
