"""Bounded process metrics: no text, criteria, identities or exception messages."""
from prometheus_client import Counter, Histogram  # type: ignore[import-not-found]

OPERATIONS = Counter("ttest_ai_execution_total", "AI execution responses, including replays",
                     ("status", "replay", "failure"))
EXECUTION_SECONDS = Histogram("ttest_ai_execution_seconds", "AI execution wall time including recovery reads")
PARSER_SECONDS = Histogram("ttest_ai_parser_seconds", "Injected intent parser wall time")
VOICE_OPERATIONS = Counter("ttest_ai_voice_execution_total", "Voice responses, not unique debits",
                           ("status", "replay", "failure"))
VOICE_EXECUTION_SECONDS = Histogram("ttest_ai_voice_execution_seconds", "Voice execution including replay/recovery",
    buckets=(.01,.05,.1,.25,.5,1,2,4,6,8,10,12,15,18,20,30,60,120))
VOICE_ASR_SECONDS = Histogram("ttest_ai_voice_asr_seconds", "Local ASR duration including rejection/cancellation",
    buckets=(.005,.01,.05,.1,.25,.5,1,2,4,6,8,10,15,20,30))
VOICE_PARSER_SECONDS = Histogram("ttest_ai_voice_parser_seconds", "Voice intent parser duration",
    buckets=(.005,.01,.05,.1,.25,.5,1,2,4,6,8,10,15,20,30))


def observe_result(result, *, counter=OPERATIONS) -> None:
    # OperationState is a validated enum contract; never use arbitrary errors
    # or request values as labels. Counts describe responses, not unique debits.
    from ..schemas.ai_search_quota import FailureCode
    code = result.operation.failure_code
    failure = code if code in {item.value for item in FailureCode} else "none"
    status = result.operation.status
    counter.labels(status if status in {"reserved", "running", "succeeded", "failed"} else "unknown",
                      "yes" if result.replay else "no", failure).inc()
