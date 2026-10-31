from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from ai_facts_pg.typed_match_cases import CASES, plan, projection

from app.services.ai_fact_quality import FactQualityPolicy, classify, counters

POLICY = FactQualityPolicy(price_max_age_seconds=60, policy_max_age_seconds=120, evidence_retention_seconds=300)
NOW = datetime(2026, 11, 1, tzinfo=UTC)


def assess(case, features, **changes):
    return classify(plan(case), projection(features), **({
        "checks": (NOW,), "source_error": False, "now": NOW, "policy": POLICY} | changes))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_verified_match_and_missing_data_are_distinct(case):
    assert assess(case, case["features"]) == "match"
    assert assess(case, []) == "unknown"
    for status in ("unknown", "legacy_unverified", "conditional", "conflict"):
        features = deepcopy(case["features"])
        features[0].update(status=status, typed_value=None)
        assert assess(case, features) == ("unknown" if status == "legacy_unverified" else status)


def test_denial_is_mismatch_but_scoped_permission_is_not_broad_denial():
    case = next(c for c in CASES if c["name"] == "pets")
    features = deepcopy(case["features"])
    features[0].update(status="explicit_deny", typed_value={"kind": "policy", "allowed": False})
    assert assess(case, features) == "mismatch"
    features[0].update(status="explicit_allow", typed_value={"kind": "policy", "allowed": True})
    features[0]["qualifiers"]["approval_required"] = True
    assert assess(case, features) == "unknown"


@pytest.mark.parametrize("checks,expected", [
    ((), "unknown"), ((None,), "unknown"), ((NOW + timedelta(seconds=1),), "stale"),
    ((NOW - timedelta(seconds=120),), "match"), ((NOW - timedelta(seconds=121),), "stale"),
])
def test_freshness_boundaries_and_missing_checks(checks, expected):
    case = next(c for c in CASES if c["name"] == "pets")
    assert assess(case, case["features"], checks=checks) == expected
    assert assess(case, case["features"], checks=checks, source_error=True) == "source_error"


def test_price_uses_shorter_window_and_counts_partition_eligible():
    case = next(c for c in CASES if c["name"] == "budget")
    assert assess(case, case["features"], checks=(NOW - timedelta(seconds=61),)) == "stale"
    result = counters(["match", "mismatch", "unknown", "stale", "source_error", "conditional", "conflict"])
    assert result["eligible"] == 7 == sum(v for k, v in result.items() if k != "eligible")
    with pytest.raises(ValueError, match="timezone"):
        assess(case, case["features"], now=NOW.replace(tzinfo=None))
