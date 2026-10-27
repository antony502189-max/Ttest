import pytest
from pydantic import ValidationError
from sqlalchemy import column, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB

from app.repositories.ai_hard_facts import hard_value_predicate
from app.schemas.ai_hard_facts import BooleanRequirement, HardValueRequirements


@pytest.mark.parametrize("data", [
    {}, {"capacity_at_least": 0}, {"capacity_at_least": True}, {"capacity_at_least": "2"},
    {"capacity_at_least": 2.5}, {"capacity_at_least": 2_147_483_648}, {"pets": True},
    {"booleans": ({"key": "balcony", "value": "true"},)},
    {"booleans": ({"key": "pets", "value": True},)},
    {"booleans": ({"key": "balcony", "value": True}, {"key": "balcony", "value": False})},
])
def test_unsupported_or_coerced_requirements_rejected(data):
    with pytest.raises(ValidationError):
        HardValueRequirements.model_validate(data)


def test_bound_parameters_and_predicate_composition():
    requirements = HardValueRequirements(capacity_at_least=3, booleans=(
        BooleanRequirement(key="balcony", value=True), BooleanRequirement(key="furnished", value=False),
    ))
    expression = hard_value_predicate(column("features", JSONB), requirements)
    query = select(column("id")).where(expression).order_by(column("paid_top").desc()).limit(20)
    sql = query.compile(dialect=postgresql.dialect())
    assert "WHERE" in str(sql) and "EXISTS" in str(sql)
    assert "ORDER BY paid_top DESC" in str(sql)
    assert "capacity_total" not in str(sql)
    assert 3 in sql.params.values()


def test_constructed_invalid_requirements_are_revalidated():
    forged = HardValueRequirements.model_construct(capacity_at_least=0)
    with pytest.raises(ValidationError):
        hard_value_predicate(column("features", JSONB), forged)
