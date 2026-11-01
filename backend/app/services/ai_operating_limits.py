"""Explicit distributed limits for text-stand.v1; never a memory fallback."""
import asyncio
import hashlib
from contextlib import asynccontextmanager, suppress
from contextvars import ContextVar
from uuid import uuid4

from redis.exceptions import RedisError

from ..schemas.ai_search_quota import QuotaSubject
from .ai_search_attempts import AIAttemptGate, AIAttemptRejected
from .rate_limit import RedisRateLimiter

AI_IP_KEY: ContextVar[str | None] = ContextVar("ai_private_ip_key", default=None)


class OperatingHTTPGate:
    def __init__(self, limiter: RedisRateLimiter):
        if not isinstance(limiter, RedisRateLimiter):
            raise TypeError("distributed Redis limiter required")
        self.limiter = limiter

    async def check(self, key: str) -> None:
        purpose = key.split(":", 1)[0]
        policies = {"ai-http": ((120, 60),), "ai-read-subject": ((60, 60),),
            "ai-guest-issue": ((2, 60), (10, 3600)), "ai-session-create": ((6, 60),)}
        if purpose not in policies:
            raise AIAttemptRejected("ABUSE_GATE_UNAVAILABLE")
        try:
            for limit, window in policies[purpose]:
                result = await self.limiter.consume(f"{key}:{window}", limit, window)
                if not result.allowed:
                    raise AIAttemptRejected("ATTEMPT_LIMIT", result.retry_after)
        except (RedisError, OSError, TimeoutError):
            raise AIAttemptRejected("ABUSE_GATE_UNAVAILABLE") from None


class OperatingAttemptGate(AIAttemptGate):
    ACQUIRE = """
    local t = redis.call('TIME')
    local now = tonumber(t[1])*1000 + math.floor(tonumber(t[2])/1000)
    for i=1,2 do redis.call('ZREMRANGEBYSCORE', KEYS[i], '-inf', now) end
    if redis.call('ZCARD', KEYS[1]) >= 4 or redis.call('ZCARD', KEYS[2]) >= 1 then return 0 end
    for i=1,2 do
      redis.call('ZADD', KEYS[i], now + 30000, ARGV[1])
      redis.call('PEXPIRE', KEYS[i], 31000)
    end
    return 1
    """
    RELEASE = """
    for i=1,2 do redis.call('ZREM', KEYS[i], ARGV[1]) end
    return 1
    """

    def __init__(self, limiter: RedisRateLimiter):
        if not isinstance(limiter, RedisRateLimiter):
            raise TypeError("distributed Redis limiter required")
        super().__init__(limiter, attempts=6, window_seconds=60)
        self.operating_limiter = limiter
        self.client = limiter._client

    async def check(self, subject: QuotaSubject) -> None:
        await super().check(subject)
        address = AI_IP_KEY.get()
        if address is None:
            raise AIAttemptRejected("ABUSE_GATE_UNAVAILABLE")
        try:
            result = await self.operating_limiter.consume(f"ai-attempt-ip:{address}", 30, 60)
            if not result.allowed:
                raise AIAttemptRejected("ATTEMPT_LIMIT", result.retry_after)
        except (RedisError, OSError, TimeoutError):
            raise AIAttemptRejected("ABUSE_GATE_UNAVAILABLE") from None

    @asynccontextmanager
    async def inference(self, subject: QuotaSubject, *, deadline: float):
        identity = hashlib.sha256(f"{subject.kind}:{subject.id}".encode()).hexdigest()
        # Common hash tag makes both keys atomic on Redis Cluster as well.
        keys = ("ai-search:{inflight}:global", f"ai-search:{{inflight}}:{identity}")
        token = uuid4().hex
        try:
            acquired = await self.client.eval(self.ACQUIRE, 2, *keys, token)
        except (RedisError, OSError, TimeoutError):
            raise AIAttemptRejected("ABUSE_GATE_UNAVAILABLE") from None
        if not acquired:
            raise AIAttemptRejected("ATTEMPT_LIMIT", 2)
        try:
            yield
        finally:
            # No cancellation cleanup beyond the operation's remaining budget.
            # Expiring tokens recover a crashed holder without releasing a peer.
            if asyncio.get_running_loop().time() < deadline:
                with suppress(RedisError, OSError, TimeoutError):
                    async with asyncio.timeout_at(min(deadline, asyncio.get_running_loop().time() + 1)):
                        await self.client.eval(self.RELEASE, 2, *keys, token)
