"""Actual distributed operating gates on an explicitly disposable Redis DB."""
import asyncio
import os
from contextlib import AsyncExitStack
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
import pytest_asyncio

from app.schemas.ai_search_quota import QuotaSubject
from app.services.ai_operating_limits import AI_IP_KEY, OperatingAttemptGate, OperatingHTTPGate
from app.services.ai_search_attempts import AIAttemptRejected
from app.services.rate_limit import RedisRateLimiter

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def limiters():
    value = os.getenv("AI_QUOTA_REDIS_TEST_URL")
    if not value:
        pytest.skip("explicit disposable Redis DB15 not configured")
    url = urlsplit(value)
    if url.hostname not in {"localhost", "127.0.0.1", "::1"} or url.path != "/15":
        pytest.fail("operating gates require disposable loopback Redis DB15")
    first, second = RedisRateLimiter(value), RedisRateLimiter(value)
    try:
        yield first, second
    finally:
        await first.close()
        await second.close()


async def test_two_workers_share_subject_and_global_inflight_caps(limiters):
    first, second = [OperatingAttemptGate(limiter) for limiter in limiters]
    subjects = [QuotaSubject(kind="auth", id=uuid4()) for _ in range(5)]
    deadline = asyncio.get_running_loop().time() + 5
    async with AsyncExitStack() as stack:
        for subject in subjects[:4]:
            await stack.enter_async_context(first.inference(subject, deadline=deadline))
        with pytest.raises(AIAttemptRejected, match="ATTEMPT_LIMIT"):
            async with second.inference(subjects[4], deadline=deadline):
                pytest.fail("fifth global slot must not open")
        with pytest.raises(AIAttemptRejected, match="ATTEMPT_LIMIT"):
            async with second.inference(subjects[0], deadline=deadline):
                pytest.fail("same subject must not open a second slot")
    async with second.inference(subjects[0], deadline=deadline):
        pass


async def test_http_issuance_limits_and_unknown_purpose_fail_closed(limiters):
    gate = OperatingHTTPGate(limiters[0])
    key = "ai-guest-issue:" + uuid4().hex
    await gate.check(key)
    await gate.check(key)
    with pytest.raises(AIAttemptRejected, match="ATTEMPT_LIMIT"):
        await gate.check(key)
    with pytest.raises(AIAttemptRejected, match="ABUSE_GATE_UNAVAILABLE"):
        await gate.check("unknown:" + uuid4().hex)


async def test_provider_attempt_requires_context_and_shares_attempt_cap(limiters):
    gates = [OperatingAttemptGate(limiter) for limiter in limiters]
    subject = QuotaSubject(kind="auth", id=uuid4())
    token = AI_IP_KEY.set("synthetic-keyed-ip-" + uuid4().hex)
    try:
        for i in range(6):
            await gates[i % 2].check(subject)
        with pytest.raises(AIAttemptRejected, match="ATTEMPT_LIMIT"):
            await gates[1].check(subject)
    finally:
        AI_IP_KEY.reset(token)
    token = AI_IP_KEY.set(None)
    try:
        with pytest.raises(AIAttemptRejected, match="ABUSE_GATE_UNAVAILABLE"):
            await gates[0].check(QuotaSubject(kind="guest", id=uuid4()))
    finally:
        AI_IP_KEY.reset(token)
