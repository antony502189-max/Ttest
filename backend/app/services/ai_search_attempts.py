"""Dedicated fail-closed AI attempt gate; never use the memory fallback here."""

import hashlib

from redis.exceptions import RedisError

from ..schemas.ai_search_quota import QuotaSubject
from .rate_limit import RedisRateLimiter


class AIAttemptRejected(Exception):
    def __init__(self, code: str, retry_after: int = 0):
        self.code, self.retry_after = code, retry_after
        super().__init__(code)


class AIAttemptGate:
    def __init__(self, limiter: RedisRateLimiter | None, *, attempts: int, window_seconds: int):
        if type(attempts) is not int or type(window_seconds) is not int or attempts < 1 or window_seconds < 1:
            raise ValueError("explicit positive technical attempt budget required")
        self.limiter, self.attempts, self.window_seconds = limiter, attempts, window_seconds

    async def check(self, subject: QuotaSubject) -> None:
        """Call before paid inference, only for a new operation, never for replay.

        Endpoint-specific IP/audio/inflight controls remain AI-09/11 requirements.
        Failure releases a reservation; it never consumes business quota.
        """
        if self.limiter is None:
            raise AIAttemptRejected("ABUSE_GATE_UNAVAILABLE")
        identity = hashlib.sha256(f"{subject.kind}:{subject.id}".encode()).hexdigest()
        try:
            result = await self.limiter.consume(f"ai-search:attempt:{identity}", self.attempts, self.window_seconds)
        except (RedisError, OSError, TimeoutError) as error:
            raise AIAttemptRejected("ABUSE_GATE_UNAVAILABLE") from error
        if not result.allowed:
            raise AIAttemptRejected("ATTEMPT_LIMIT", result.retry_after)
