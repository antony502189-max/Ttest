"""Execute the shared full typed plan in PostgreSQL; no provider/catalog access."""
import copy

import pytest
from sqlalchemy import literal, select
from sqlalchemy.dialects.postgresql import JSONB
from typed_match_cases import CASES, edge_cases, plan, projection

from app.repositories.ai_hard_matching import hard_match_predicate
from app.services.ai_hard_matching import evaluate_hard_match

pytestmark = pytest.mark.integration


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
