"""Execute the shared full typed plan in PostgreSQL; no provider/catalog access."""
import copy
from uuid import uuid4

import pytest
from sqlalchemy import literal, select
from sqlalchemy.dialects.postgresql import JSONB
from typed_match_cases import CASES, VOCABULARY, edge_cases, intent, plan, projection

from app.repositories.ai_hard_matching import hard_match_predicate
from app.services.ai_hard_matching import compile_hard_match, evaluate_hard_match

pytestmark = pytest.mark.integration


def test_apartment_island_and_general_pet_permission_use_verified_facts(pg):
    engine, _ = pg
    request = intent({
        "accommodation": {"strength": "hard", "value": {"kind": "apartment"}},
        "geography": {"strength": "hard", "value": {"province_code": "38", "island": "tenerife"}},
        "pets": {"strength": "hard", "value": {"kind": "general_permission"}},
    })
    compiled = compile_hard_match(request, VOCABULARY)

    def fact(key, value, qualifiers=None, status="explicit_allow"):
        return {"key": key, "qualifiers": qualifiers or {}, "status": status, "typed_value": value,
                "supporting_fact_ids": [str(uuid4())]}

    apartment = fact("accommodation", {"kind": "category", "value": "one_bedroom"})
    studio = fact("accommodation", {"kind": "category", "value": "studio"})
    room = fact("accommodation", {"kind": "category", "value": "room"})
    tenerife = fact("geography", {"kind": "geography", "province_code": "38", "municipality_code": "38001"})
    la_palma = fact("geography", {"kind": "geography", "province_code": "38", "municipality_code": "38037"})
    province_only = fact("geography", {"kind": "geography", "province_code": "38"})
    allowed = fact("pets", {"kind": "policy", "allowed": True})
    scoped = fact("pets", {"kind": "policy", "allowed": True}, {"species": "dog"})
    approval = fact("pets", None, {"approval_required": True}, "conditional")
    denied = fact("pets", {"kind": "policy", "allowed": False}, {"species": "cat"}, "explicit_deny")

    with engine.connect() as connection:
        for features, matches, covered in [
            ([apartment, tenerife, allowed], True, True),
            ([studio, tenerife, allowed], True, True),
            ([room, tenerife, allowed], False, True),
            ([apartment, la_palma, allowed], False, True),
            ([apartment, province_only, allowed], False, False),
            ([apartment, tenerife, scoped], False, False),
            ([apartment, tenerife, approval], False, False),
            ([apartment, tenerife, allowed, denied], False, False),
        ]:
            assert (not evaluate_hard_match(compiled, projection(features))) is matches
            value = literal(features, type_=JSONB)
            assert connection.scalar(select(hard_match_predicate(value, compiled))) is matches
            assert connection.scalar(select(hard_match_predicate(value, compiled, coverage=True))) is covered


def test_age_neutral_headcount_sql_preserves_capacity_and_availability_guards(pg):
    engine, _ = pg
    features = copy.deepcopy([f for f in next(c for c in CASES if c['name'] == 'party')['features']
                             if f['key'] in {'capacity_total', 'available_spots'}])
    for f in features:
        f['typed_value']['value'] = 1
    with engine.connect() as connection:
        for persons in [1, 2]:
            compiled = compile_hard_match(intent({'party': {'strength': 'hard', 'value': {'persons': persons}}}), VOCABULARY)
            for values in [features, features[:1], features[1:], [], features + [features[0]]]:
                if len(values) <= 2:
                    expected = not evaluate_hard_match(compiled, projection(values))
                else:
                    expected = False
                assert connection.scalar(select(hard_match_predicate(literal(values, type_=JSONB), compiled))) is expected


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_known_fact_coverage_is_distinct_from_matching_and_unknown(pg, case):
    engine, _ = pg
    compiled = plan(case)
    with engine.connect() as connection:
        def covered(features):
            return connection.scalar(select(hard_match_predicate(literal(features, type_=JSONB), compiled, coverage=True)))
        assert covered(case["features"]) is True
        assert covered([]) is False
        for status in ("unknown", "conditional", "conflict", "legacy_unverified"):
            changed = copy.deepcopy(case["features"])
            changed[0].update(status=status, typed_value=None)
            assert covered(changed) is False
        changed = copy.deepcopy(case["features"])
        if changed[0]["typed_value"]["kind"] == "policy":
            changed[0].update(status="explicit_deny")
            changed[0]["typed_value"]["allowed"] = False
            assert covered(changed) is True
            assert connection.scalar(select(hard_match_predicate(literal(changed, type_=JSONB), compiled))) is False


def test_price_coverage_keeps_period_currency_and_ignores_budget_threshold(pg):
    engine, _ = pg
    case = next(c for c in CASES if c["name"] == "budget")
    features = copy.deepcopy(case["features"])
    features[0]["typed_value"]["amount"] = "999999.00"
    with engine.connect() as connection:
        compiled = plan(case)
        assert connection.scalar(select(hard_match_predicate(literal(features, type_=JSONB), compiled, coverage=True))) is True
        for field, value in (("period", "nightly"), ("currency", "USD")):
            changed = copy.deepcopy(features)
            changed[0]["typed_value"][field] = value
            assert connection.scalar(select(hard_match_predicate(literal(changed, type_=JSONB), compiled, coverage=True))) is False


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_sql_and_typed_match_agree_on_all_criteria(pg, case):
    engine, _ = pg
    compiled = plan(case)
    cases = [case["features"], []]
    for status in ("unknown", "conditional", "conflict", "legacy_unverified"):
        changed = copy.deepcopy(case["features"])
        changed[0].update(status=status, typed_value=None)
        cases.append(changed)
    with engine.connect() as connection:
        for features in cases:
            expected = not evaluate_hard_match(compiled, projection(features))
            for value in (features, projection(features).model_dump(mode="json")["features"]):
                for key_prefilter in (True, False):
                    assert connection.scalar(select(hard_match_predicate(literal(value, type_=JSONB), compiled,
                        key_prefilter=key_prefilter))) is expected
        # Duplicated/invalid stored relevant feature never counts as confirmation.
        for bad in (None, {}, "bad", case["features"] + [case["features"][0]]):
            for key_prefilter in (True, False):
                assert connection.scalar(select(hard_match_predicate(literal(bad, type_=JSONB), compiled,
                    key_prefilter=key_prefilter))) is False


@pytest.mark.parametrize("case,features,expected", edge_cases())
def test_sql_semantic_boundaries(pg, case, features, expected):
    engine, _ = pg
    with engine.connect() as connection:
        assert connection.scalar(select(hard_match_predicate(literal(features, type_=JSONB), plan(case)))) is expected


@pytest.mark.parametrize("bad", [None, [], "bad", True, 3, {"approval_required": True}])
def test_corrupt_value_and_scope_never_raise_or_match(pg, bad):
    engine, _ = pg
    case = next(c for c in CASES if c["name"] == "pets")
    with engine.connect() as connection:
        for field in ("typed_value", "qualifiers"):
            features = copy.deepcopy(case["features"])
            features[0][field] = bad
            assert connection.scalar(select(hard_match_predicate(literal(features, type_=JSONB), plan(case)))) is False


@pytest.mark.parametrize("bad", ["2 OR 1=1", "nan", "1e10000", "9999999999999999999999999999999", True, [], {}])
def test_numeric_casts_are_guarded(pg, bad):
    engine, _ = pg
    with engine.connect() as connection:
        for name, field in (("budget", "amount"), ("party", "value")):
            case = next(c for c in CASES if c["name"] == name)
            features = copy.deepcopy(case["features"])
            features[0]["typed_value"][field] = bad
            assert connection.scalar(select(hard_match_predicate(literal(features, type_=JSONB), plan(case)))) is False


def test_full_typed_predicate_precedes_count_order_seek_and_limit(pg):
    from sqlalchemy import Column, Integer, MetaData, Table, func
    engine, _ = pg
    case = next(c for c in CASES if c["name"] == "pets")
    candidates = Table("typed_candidates", MetaData(), Column("id", Integer, primary_key=True),
                       Column("paid_rank", Integer), Column("features", JSONB))
    valid = case["features"]
    invalid = copy.deepcopy(valid)
    invalid[0]["qualifiers"]["max_count"] = 1
    with engine.begin() as connection:
        candidates.create(connection)
        connection.execute(candidates.insert(), [
            {"id": 1, "paid_rank": 100, "features": invalid}, {"id": 2, "paid_rank": 90, "features": []},
            {"id": 3, "paid_rank": 70, "features": valid}, {"id": 4, "paid_rank": 20, "features": valid}])
        eligible = select(candidates.c.id, candidates.c.paid_rank).where(
            hard_match_predicate(candidates.c.features, plan(case)))
        assert connection.scalar(select(func.count()).select_from(eligible.subquery())) == 2
        first = connection.execute(eligible.order_by(candidates.c.paid_rank.desc()).limit(1)).one()
        assert first.id == 3
        second = connection.execute(eligible.where(candidates.c.paid_rank < first.paid_rank).order_by(
            candidates.c.paid_rank.desc()).limit(1)).one()
        assert second.id == 4


@pytest.mark.parametrize("bad", [None, [], "bad", True, 3, {}, {"max_count": 1}])
def test_key_prefilter_retains_malformed_duplicates_and_unrelated_rows(pg, bad):
    engine, _ = pg
    case = next(c for c in CASES if c["name"] == "pets")
    malformed = copy.deepcopy(case["features"][0])
    malformed["qualifiers"] = bad
    with engine.connect() as connection:
        values = [case["features"] + [extra] for extra in
                  (malformed, {**malformed, "key": "unrelated"}, [malformed], {"key": ["pets"]}, {}, None, "pets")]
        values += [[case["features"]], [[[case["features"][0]]]]]
        for value in values:
            old = connection.scalar(select(hard_match_predicate(literal(value, type_=JSONB), plan(case), key_prefilter=False)))
            new = connection.scalar(select(hard_match_predicate(literal(value, type_=JSONB), plan(case))))
            assert new is old
