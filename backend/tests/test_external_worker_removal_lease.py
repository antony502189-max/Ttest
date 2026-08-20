from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.workers import external_listings as worker


class RenewableRedis:
    def __init__(self, value: str = "owner") -> None:
        self.value = value
        self.refreshes = 0

    async def eval(self, script: str, _keys: int, _key: str, token: str, *args: str) -> int:
        if self.value != token:
            return 0
        if "EXPIRE" in script:
            self.refreshes += 1
            return 1
        if "DEL" in script:
            self.value = ""
            return 1
        return 0


def settings() -> SimpleNamespace:
    return SimpleNamespace(external_worker_stale_after_seconds=300)


def test_long_removal_probe_refreshes_heartbeat_and_owned_redis_lease(monkeypatch):
    async def verify() -> None:
        redis = RenewableRedis()
        heartbeats: list[dict] = []

        async def record_state(**kwargs):
            heartbeats.append(kwargs)
            return SimpleNamespace()

        async def slow_probe() -> int:
            await asyncio.sleep(0.045)
            return 7

        monkeypatch.setattr(worker, "get_settings", settings)
        monkeypatch.setattr(worker, "worker_state", record_state)

        result = await worker._run_removal_probe_with_lease(
            slow_probe(),
            redis=redis,
            lock_key="lock",
            token="owner",
            lock_ttl=1800,
            heartbeat_interval=0.01,
        )

        assert result == 7
        assert len(heartbeats) >= 3
        assert all(item == {} for item in heartbeats)
        assert redis.refreshes >= 3

    asyncio.run(verify())


def test_removal_probe_stops_if_redis_lease_is_no_longer_owned(monkeypatch):
    async def verify() -> None:
        redis = RenewableRedis(value="another-worker")
        cancelled = asyncio.Event()

        async def record_state(**_kwargs):
            return SimpleNamespace()

        async def blocked_probe() -> int:
            try:
                await asyncio.sleep(1)
                return 1
            finally:
                cancelled.set()

        monkeypatch.setattr(worker, "get_settings", settings)
        monkeypatch.setattr(worker, "worker_state", record_state)

        with pytest.raises(RuntimeError, match="external removal lock lost"):
            await worker._run_removal_probe_with_lease(
                blocked_probe(),
                redis=redis,
                lock_key="lock",
                token="owner",
                lock_ttl=1800,
                heartbeat_interval=0.01,
            )

        assert cancelled.is_set()
        assert redis.refreshes == 0

    asyncio.run(verify())
