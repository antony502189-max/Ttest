"""Candidate and matching populations share distinct statement-local SQL names."""
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql

from app.models import Listing
from app.repositories.ai_verified_cards import (
    _candidate_cohorts,
    _materialized_candidates,
    verified_coverage_predicate,
    verified_intent_predicate,
)
from app.repositories.listings import apply_search_filters, visible_query
from app.schemas.ai_search_intent import Criteria, SearchIntent
from app.schemas.listings import ListingCardSearchRequest
from demo.entry import pipeline


@pytest.mark.parametrize("coverage", [False, True])
def test_repeated_candidate_count_compilation_keeps_independent_cte_roles(coverage):
    facts = pipeline(None)
    predicate = verified_coverage_predicate if coverage else verified_intent_predicate
    for amount in (None, "700", "600", None):
        values = {"rental_mode": {"strength": "hard", "value": "long"}}
        if amount is not None:
            values["budget"] = {"strength": "hard", "value": {
                "amount": amount, "currency": "EUR", "period": "monthly"}}
        intent = SearchIntent(schema_version="ai-search.v1", taxonomy_version="rental.v1",
            session_id=uuid4(), version=0, criteria=Criteria.model_validate(values))
        payload = ListingCardSearchRequest()
        base = _materialized_candidates(apply_search_filters(visible_query(), payload))
        filtered = base.where(predicate(facts, intent, cohort_scope=_candidate_cohorts(base, facts)))
        count = select(func.count()).select_from(filtered.with_only_columns(Listing.id).order_by(None).subquery())
        sql = str(count.compile(dialect=postgresql.dialect()))
        assert sql.count("ai_candidate_ids AS MATERIALIZED") == 1
        assert sql.count("ai_matching_cohorts AS MATERIALIZED") == 1
