from app.commands.audit_long_term_policy import classify


def test_read_only_policy_inventory_classifies_long_and_holiday_separately():
    assert classify("long", 1) == "eligible_long_term"
    assert classify("long", 999) == "eligible_long_term"
    assert classify("long", 1000) == "eligible_long_term"
    assert classify("long", 1001) == "long_term_above_ceiling"
    assert classify("long", None) == "missing_or_invalid_monthly_price"
    assert classify("long", 0) == "missing_or_invalid_monthly_price"
    assert classify("holiday", 50) == "holiday_or_unsupported"
    assert classify("unknown", 900) == "holiday_or_unsupported"
