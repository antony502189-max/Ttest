import pytest

from app.services.ai_migration_limits import migration_limits


@pytest.mark.parametrize("arguments", [{"lock_timeout_ms": "0"}, {"statement_timeout_ms": "0"},
    {"lock_timeout_ms": "5000; DROP TABLE listings"}, {"lock_timeout_ms": "５０００"},
    {"statement_timeout_ms": "99999999999"}, {"lock_timeout_ms": "30001"},
    {"lock_timeout_ms": "5000", "statement_timeout_ms": "5000"}])
def test_unsafe_or_unbounded_migration_timeout_is_rejected(arguments):
    with pytest.raises(ValueError, match="MIGRATION_TIMEOUT_POLICY_INVALID"):
        migration_limits(arguments)


def test_bounded_operator_window_and_safe_defaults():
    assert migration_limits({}) == (5000, 60000)
    assert migration_limits({"lock_timeout_ms": "300", "statement_timeout_ms": "5000"}) == (300, 5000)
