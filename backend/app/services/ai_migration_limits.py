"""Bounded DDL admission. A timeout aborts the transaction, never removes guards."""


def migration_limits(arguments: dict[str, str]) -> tuple[int, int]:
    values = []
    for name, default, maximum in (("lock_timeout_ms", "5000", 30000),
                                    ("statement_timeout_ms", "60000", 300000)):
        value = arguments.get(name, default)
        if not isinstance(value, str) or not value.isascii() or not value.isdigit() or len(value) > 6:
            raise ValueError("MIGRATION_TIMEOUT_POLICY_INVALID")
        number = int(value)
        if not 100 <= number <= maximum:
            raise ValueError("MIGRATION_TIMEOUT_POLICY_INVALID")
        values.append(number)
    if values[0] >= values[1]:
        raise ValueError("MIGRATION_TIMEOUT_POLICY_INVALID")
    return values[0], values[1]
