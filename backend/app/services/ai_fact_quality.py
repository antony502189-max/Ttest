"""Explicit closed-catalog quality policy; no default TTL or public activation."""
from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Literal

from pydantic import Field

from ..schemas.ai_listing_facts import Contract, SearchProjection
from .ai_hard_matching import HardMatchPlan, evaluate_hard_match

Quality = Literal["match", "mismatch", "unknown", "conditional", "conflict", "stale", "source_error"]


class FactQualityPolicy(Contract):
    price_max_age_seconds: int = Field(gt=0, le=31_536_000)
    policy_max_age_seconds: int = Field(gt=0, le=31_536_000)
    evidence_retention_seconds: int = Field(gt=0, le=31_536_000)

    def max_age(self, plan: HardMatchPlan) -> timedelta:
        keys = {r.key for c in plan.criteria for r in c.rules}
        seconds = self.policy_max_age_seconds
        if keys & {"price", "availability", "available_spots"}:
            seconds = min(seconds, self.price_max_age_seconds)
        return timedelta(seconds=seconds)


def aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware instant required")
    return value


def classify(plan: HardMatchPlan, projection: SearchProjection | None, *,
             checks: tuple[datetime | None, ...], source_error: bool,
             now: datetime, policy: FactQualityPolicy) -> Quality:
    """One mutually exclusive bucket; only a structurally supported failure is mismatch.

    Used on an entire bounded eligible cohort, never a post-LIMIT card filter.
    Caller must attest projection currentness and source membership at one snapshot.
    """
    aware(now)
    policy = FactQualityPolicy.model_validate(policy)
    if source_error:
        return "source_error"
    if not checks or any(t is None for t in checks):
        return "unknown"
    if any(aware(t) > now or now - t > policy.max_age(plan) for t in checks if t is not None):
        return "stale"
    if projection is None:
        return "unknown"
    projection = SearchProjection.model_validate(projection.model_dump())
    reasons: set[str] = set()
    for group in plan.criteria:
        for rule in group.rules:
            one = HardMatchPlan((replace(group, rules=(rule,)),))
            if not evaluate_hard_match(one, projection):
                continue
            peers = [f for f in projection.features if f.key == rule.key and all(
                getattr(f.qualifiers, k) in values for k, values in rule.scopes)]
            if len(peers) != 1:
                reasons.add("unknown")
                continue
            fact = peers[0]
            if fact.status in {"conditional", "conflict"}:
                reasons.add(fact.status)
                continue
            if fact.status not in {"explicit_allow", "explicit_deny"}:
                reasons.add("unknown")
                continue
            # Reuse the matcher for scope/qualifier/kind coverage. A denial is
            # normalized only in this detached diagnostic shape, never stored.
            data = projection.model_dump()
            for feature in data["features"]:
                if feature["key"] == fact.key and feature["qualifiers"] == fact.qualifiers.model_dump():
                    feature["status"] = "explicit_allow"
                    if fact.status == "explicit_deny":
                        feature["typed_value"] = {"kind": "policy", "allowed": True}
            shape = SearchProjection.model_validate(data)
            structural = HardMatchPlan((replace(group, rules=(replace(rule, tests=()),)),))
            reasons.add("unknown" if evaluate_hard_match(structural, shape) else "mismatch")
    # Uncertainty takes priority over a known failed criterion: no false claim
    # that the complete requested criteria were checked against verified data.
    priority: tuple[Quality, ...] = ("conflict", "conditional", "unknown", "mismatch")
    for reason in priority:
        if reason in reasons:
            return reason
    return "match"


def counters(outcomes: list[Quality]) -> dict[str, int]:
    counts = Counter(outcomes)
    return {"eligible": len(outcomes), **{key: counts[key] for key in (
        "match", "mismatch", "unknown", "conditional", "conflict", "stale", "source_error")}}
