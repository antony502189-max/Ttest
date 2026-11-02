"""Private outcome values must never create unbounded metric labels."""
from types import SimpleNamespace

from prometheus_client import generate_latest

from app.services.ai_observability import observe_result


def test_unknown_private_failure_is_suppressed_in_metric_labels():
    secret = "private-criteria-and-provider-body-canary"
    observe_result(SimpleNamespace(operation=SimpleNamespace(status="failed", failure_code=secret), replay=True))
    payload = generate_latest().decode()
    assert secret not in payload
    assert 'failure="none",replay="yes",status="failed"' in payload


def test_fixed_failure_has_a_bounded_metric_code():
    observe_result(SimpleNamespace(operation=SimpleNamespace(status="failed", failure_code="LLM_FAILURE"), replay=False))
    assert 'failure="LLM_FAILURE",replay="no",status="failed"' in generate_latest().decode()
