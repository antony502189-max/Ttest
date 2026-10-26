"""Execute the actual SQL on synthetic data; no catalog/provider access."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, func, literal, select
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.ai_listing_facts import AiListingSearchFeatures
from app.repositories.ai_hard_facts import hard_value_predicate
from app.schemas.ai_hard_facts import BooleanRequirement, HardValueRequirements
from app.schemas.ai_listing_facts import Qualifiers, SearchFeature

pytestmark = pytest.mark.integration


def capacity(value=3, **changes):
    return {
        "key": "capacity_total", "status": "explicit_allow",
        "qualifiers": {"inventory_scope": "rented_unit"},
        "typed_value": {"kind": "quantity", "value": value, "unit": "persons"},
        "supporting_fact_ids": [str(uuid4())], **changes,
    }


def boolean(key="balcony", value=True, **changes):
    return {"key": key, "status": "explicit_allow", "qualifiers": {},
            "typed_value": {"kind": "boolean", "value": value},
            "supporting_fact_ids": [str(uuid4())], **changes}


def test_capacity_values_scopes_statuses_and_malformed_json(pg):
    engine, _ = pg
    requirements = HardValueRequirements(capacity_at_least=2)
    cases = [(None, False), ({}, False), ("bad", False), ([], False), ([capacity(1)], False),
             ([capacity(2)], True), ([capacity(3)], True), ([capacity(2_147_483_647)], True)]
    cases += [([capacity(value)], False) for value in (
        None, True, "3", "3 OR 1=1", 0, -1, 2.5, 3.0, 2_147_483_648, 10**100,
    )]
    cases += [([capacity(status=status)], False) for status in (
        "unknown", "conditional", "conflict", "legacy_unverified", "explicit_deny",
    )]
    cases += [([capacity(qualifiers=scope)], False) for scope in (
        {}, None, [], {"inventory_scope": "shared_building"},
        {"inventory_scope": "rented_unit", "approval_required": True},
    )]
    cases += [([capacity(key=key)], False) for key in ("available_spots", "current_room_residents")]
    cases += [([capacity(typed_value=value)], False) for value in (
        None, [], {"kind": "quantity", "value": 3, "unit": "months"},
        {"kind": "money", "value": 3, "unit": "persons"},
    )]
    cases += [([capacity(), capacity(status="conflict", typed_value=None)], False),
              ([capacity(), capacity(qualifiers={})], False), ([capacity()] * 129, False)]
    # Actual DTO serialization retains null qualifier fields; these are equivalent
    # to absent optional qualifiers, and must not cause a false rejection.
    serialized = SearchFeature.model_validate_json(json.dumps(capacity())).model_dump(mode="json")
    assert serialized["qualifiers"] == Qualifiers(inventory_scope="rented_unit").model_dump()
    cases.append(([serialized], True))
    with engine.connect() as connection:
        for features, expected in cases:
            predicate = hard_value_predicate(literal(features, type_=JSONB), requirements)
            assert connection.scalar(select(predicate)) is expected, features
        # SQL NULL is different from JSON null.
        assert connection.scalar(select(hard_value_predicate(
            literal(None, type_=JSONB(none_as_null=True)), requirements,
        ))) is False


@pytest.mark.parametrize("key", ["furnished", "bills_included", "balcony", "terrace"])
@pytest.mark.parametrize("wanted", [True, False])
def test_boolean_exact_values_and_uncertainty(pg, key, wanted):
    engine, _ = pg
    requirements = HardValueRequirements(booleans=(BooleanRequirement(key=key, value=wanted),))
    good = boolean(key, wanted)
    cases = [([good], True), ([boolean(key, not wanted)], False), ([], False),
             ([boolean("pets", wanted)], False), ([boolean(key, str(wanted).lower())], False),
             ([good, good], False), ([boolean(key, wanted, qualifiers={"approval_required": True})], False)]
    cases += [([boolean(key, wanted, status=status)], False) for status in (
        "unknown", "conditional", "conflict", "legacy_unverified", "explicit_deny",
    )]
    with engine.connect() as connection:
        for features, expected in cases:
            assert connection.scalar(select(hard_value_predicate(
                literal(features, type_=JSONB), requirements,
            ))) is expected, features


def test_predicates_before_count_commercial_order_seek_and_limit(pg):
    engine, _ = pg
    projection = AiListingSearchFeatures.__table__
    candidates = Table("offline_candidates", MetaData(), Column("id", UUID, primary_key=True),
                       Column("paid_rank", Integer, nullable=False))
    requirements = HardValueRequirements(capacity_at_least=2, booleans=(
        BooleanRequirement(key="balcony", value=True), BooleanRequirement(key="furnished", value=False),
    ))
    # Several high-ranked incompatible rows precede valid candidates; post-page
    # filtering would incorrectly yield an empty page/count.
    data = [(100, [capacity(1), boolean(), boolean("furnished", False)]),
            (99, [capacity(), boolean(status="conditional"), boolean("furnished", False)]),
            (98, [capacity(), boolean(), boolean("furnished", True)]),
            (70, [capacity(2), boolean(), boolean("furnished", False)]),
            (20, [capacity(3), boolean(), boolean("furnished", False)])]
    with engine.begin() as connection:
        candidates.create(connection)
        ids = []
        for rank, features in data:
            identity = uuid4()
            ids.append(identity)
            connection.execute(candidates.insert().values(id=identity, paid_rank=rank))
            connection.execute(projection.insert().values(
                canonical_listing_id=identity, feature_revision=1, schema_version="ai-facts.v1",
                taxonomy_version="ai-search.v1", resolver_version="test.v1", input_hash="a" * 64,
                computed_at=datetime.now(UTC), features=features,
            ))
        # No projection is never interpreted as permission.
        connection.execute(candidates.insert().values(id=uuid4(), paid_rank=101))
        source = candidates.join(projection, candidates.c.id == projection.c.canonical_listing_id)
        eligible = select(candidates.c.id, candidates.c.paid_rank).select_from(source).where(
            hard_value_predicate(projection.c.features, requirements),
        )
        assert connection.scalar(select(func.count()).select_from(eligible.subquery())) == 2
        first = connection.execute(eligible.order_by(candidates.c.paid_rank.desc()).limit(1)).one()
        assert first.id == ids[3]
        second = connection.execute(eligible.where(candidates.c.paid_rank < first.paid_rank).order_by(
            candidates.c.paid_rank.desc(),
        ).limit(1)).one()
        assert second.id == ids[4]
