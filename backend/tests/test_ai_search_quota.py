import hashlib
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from redis.exceptions import RedisError

from app.schemas.ai_search_quota import LeasePolicy, QuotaOperation, QuotaSubject, ResultReceipt
from app.services.ai_search_attempts import AIAttemptGate, AIAttemptRejected
from app.services.rate_limit import RateLimitResult, RedisRateLimiter


def operation(**changes):
    return QuotaOperation(
        **{
            "idempotency_key": uuid4(),
            "channel": "text",
            "payload_sha256": hashlib.sha256(b"synthetic").hexdigest(),
            "session_id": uuid4(),
            "expected_session_version": 0,
            **changes,
        }
    )


def test_fingerprint_binds_body_channel_session_and_version_but_not_retry_key():
    op = operation()
    assert op.fingerprint() == op.model_copy(update={"idempotency_key": uuid4()}).fingerprint()
    for update in (
        {"channel": "voice"},
        {"payload_sha256": "a" * 64},
        {"filters_sha256": "b" * 64},
        {"session_id": uuid4()},
        {"expected_session_version": 1},
    ):
        assert op.fingerprint() != op.model_copy(update=update).fingerprint()


@pytest.mark.parametrize(
    "changes",
    [
        {"expected_session_version": True},
        {"expected_session_version": "1"},
        {"expected_session_version": -1},
        {"payload_sha256": "not-a-hash"},
        {"channel": "video"},
        {"quota": 200},
        {"raw_text": "no"},
    ],
)
def test_strict_internal_operation(changes):
    with pytest.raises(ValidationError):
        operation(**changes)


def test_receipt_is_bounded_and_contains_no_arbitrary_payload():
    for invalid in (
        {"result_ref": uuid4(), "count": True},
        {"result_ref": uuid4(), "count": -1},
        {"result_ref": uuid4(), "count": 0, "transcript": "no"},
    ):
        with pytest.raises(ValidationError):
            ResultReceipt(**invalid)
    with pytest.raises(ValidationError):
        LeasePolicy(reservation_seconds=True, running_seconds=15, recovery_grace_seconds=30)


@pytest.mark.parametrize("outage", [None, RedisError("offline"), OSError("offline"), TimeoutError()])
async def test_ai_attempts_fail_closed(outage):
    limiter = None if outage is None else AsyncMock(spec=RedisRateLimiter)
    if limiter is not None:
        limiter.consume.side_effect = outage
    gate = AIAttemptGate(limiter, attempts=5, window_seconds=60)
    with pytest.raises(AIAttemptRejected, match="ABUSE_GATE_UNAVAILABLE"):
        await gate.check(QuotaSubject(kind="guest", id=uuid4()))


async def test_attempt_gate_rejects_and_uses_separate_namespace():
    limiter = AsyncMock(spec=RedisRateLimiter)
    limiter.consume.return_value = RateLimitResult(False, 12)
    gate = AIAttemptGate(limiter, attempts=5, window_seconds=60)
    subject = QuotaSubject(kind="guest", id=uuid4())
    with pytest.raises(AIAttemptRejected) as error:
        await gate.check(subject)
    assert (error.value.code, error.value.retry_after) == ("ATTEMPT_LIMIT", 12)
    key, count, seconds = limiter.consume.call_args.args
    assert key.startswith("ai-search:attempt:") and str(subject.id) not in key
    assert (count, seconds) == (5, 60)
    limiter.consume.return_value = RateLimitResult(True)
    await gate.check(subject)
