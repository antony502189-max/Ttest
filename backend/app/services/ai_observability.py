"""Bounded process metrics: no text, criteria, identities or exception messages."""
from prometheus_client import Counter, Histogram  # type: ignore[import-not-found]

OPERATIONS = Counter("ttest_ai_execution_total", "AI execution responses, including replays",
                     ("status", "replay", "failure"))
EXECUTION_SECONDS = Histogram("ttest_ai_execution_seconds", "AI execution wall time including recovery reads")
PARSER_SECONDS = Histogram("ttest_ai_parser_seconds", "Injected intent parser wall time")


def observe_result(result) -> None:
    # OperationState is a validated enum contract; never use arbitrary errors
    # or request values as labels. Counts describe responses, not unique debits.
    from ..schemas.ai_search_quota import FailureCode
    code = result.operation.failure_code
    failure = code if code in {item.value for item in FailureCode} else "none"
    status = result.operation.status
    OPERATIONS.labels(status if status in {"reserved", "running", "succeeded", "failed"} else "unknown",
                      "yes" if result.replay else "no", failure).inc()
