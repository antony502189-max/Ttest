"""Actual card price/mode cannot contradict a verified hard budget/mode."""
import json
from uuid import uuid4

import pytest
from sqlalchemy import Boolean, Column, Integer, MetaData, String, Table, select

from app.repositories.ai_card_values import current_card_values_predicate
from app.schemas.ai_search_intent import SearchIntent

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("period,column", [("monthly", "monthly_price"), ("nightly", "nightly_price"), ("weekly", "weekly_price")])
def test_exact_period_price_and_current_mode_are_required(pg, period, column):
    engine, _ = pg
    table = Table("card_price_fixture", MetaData(), Column("id", Integer, primary_key=True),
        Column("rental_mode", String), Column("monthly_price", Integer), Column("nightly_price", Integer), Column("weekly_price", Integer), Column("source_price_currency", String), Column("source_price_is_from", Boolean))
    request = SearchIntent.model_validate_json(json.dumps({"schema_version": "ai-search.v1", "taxonomy_version": "rental.v1",
        "session_id": str(uuid4()), "version": 0, "criteria": {
            "rental_mode": {"strength": "hard", "value": "long"},
            "budget": {"strength": "hard", "value": {"amount": "700.00", "currency": "EUR", "period": period}}}}))
    with engine.begin() as connection:
        table.create(connection)
        connection.execute(table.insert(), [{"id": i, "rental_mode": mode, column: value} for i, (mode, value) in enumerate(
            (("long", 700), ("long", 701), ("long", None), ("holiday", 700), ("long", -1)), start=1)])
        query = select(table.c.id).where(current_card_values_predicate(request, columns=table.c))
        assert connection.scalars(query).all() == [1]
        for changes in ({"source_price_currency": "USD"}, {"source_price_is_from": True}):
            connection.execute(table.update().where(table.c.id == 1).values(**changes))
            assert connection.scalars(query).all() == []
            connection.execute(table.update().where(table.c.id == 1).values(
                source_price_currency=None, source_price_is_from=None))
