from __future__ import annotations

import asyncio
from collections import OrderedDict, deque
from dataclasses import dataclass
from time import monotonic

from redis.exceptions import RedisError

from ..core.config import get_settings


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after: int = 0


class MemoryRateLimiter:
    """Single-process bounded fallback used when Redis is unavailable."""

    def __init__(self, max_keys: int = 10_000) -> None:
        self._attempts: OrderedDict[str, deque[float]] = OrderedDict()
        self._max_keys = max_keys
        self._lock = asyncio.Lock()

    async def consume(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = monotonic()
        async with self._lock:
            attempts = self._attempts.get(key)
            if attempts is None:
                if len(self._attempts) >= self._max_keys:
                    self._attempts.popitem(last=False)
                attempts = deque()
                self._attempts[key] = attempts
            else:
                self._attempts.move_to_end(key)

            while attempts and attempts[0] <= now - window_seconds:
                attempts.popleft()
            if len(attempts) >= limit:
                return RateLimitResult(False, max(1, int(window_seconds - (now - attempts[0]))))
            attempts.append(now)
        return RateLimitResult(True)


class RedisRateLimiter:
    """Atomic fixed-window limiter shared by all backend instances."""

    _SCRIPT = """
    local current = redis.call('INCR', KEYS[1])
    if current == 1 then
      redis.call('EXPIRE', KEYS[1], ARGV[1])
    end
    local ttl = redis.call('TTL', KEYS[1])
    return {current, ttl}
    """

    def __init__(self, url: str) -> None:
        try:
            from redis.asyncio import from_url
        except ImportError as error:  # pragma: no cover - configuration error
            raise RuntimeError("redis is required when REDIS_URL is configured") from error
        self._client = from_url(
            url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
            health_check_interval=30,
        )

    async def consume(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        current, ttl = await self._client.eval(self._SCRIPT, 1, key, window_seconds)
        allowed = int(current) <= limit
        return RateLimitResult(allowed, 0 if allowed else max(1, int(ttl)))

    async def ping(self) -> bool:
        return bool(await self._client.ping())

    async def close(self) -> None:
        await self._client.aclose()


class ResilientRateLimiter:
    """Uses Redis when healthy and temporarily falls back after an outage."""

    def __init__(self) -> None:
        settings = get_settings()
        self._memory = MemoryRateLimiter()
        self._redis = RedisRateLimiter(settings.redis_url) if settings.redis_url else None
        self._redis_retry_at = 0.0

    async def consume(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = monotonic()
        if self._redis and now >= self._redis_retry_at:
            try:
                return await self._redis.consume(key, limit, window_seconds)
            except (RedisError, OSError, asyncio.TimeoutError):
                self._redis_retry_at = now + 5
        return await self._memory.consume(key, limit, window_seconds)

    async def ready(self) -> bool:
        if not self._redis:
            return True
        try:
            return await self._redis.ping()
        except (RedisError, OSError, asyncio.TimeoutError):
            return False

    async def close(self) -> None:
        if self._redis:
            await self._redis.close()
