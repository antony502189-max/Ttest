from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.workers import external_listings as worker


class BusyRedis:
    async def set(self, *args, **kwargs) -> bool:
        return False

    async def get(self, *args, **kwargs):
        return None

    async def aclose(self) -> None:
        return None


def worker_settings(**overrides):
    values = {
        "external_import_enabled": True,
        "external_removal_check_enabled": True,
        "external_import_interval_seconds": 7200,
        "external_removal_check_interval_seconds": 900,
        "external_import_run_on_start": True,
        "redis_url": "redis://test",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_replica_without_redis_lock_does_not_publish_running_heartbeat(monkeypatch):
    async def verify() -> None:
        states: list[dict] = []

        async def record_state(**kwargs):
            states.append(kwargs)
            return SimpleNamespace()

        monkeypatch.setattr(worker, "get_settings", lambda: worker_settings())
        monkeypatch.setattr(worker, "from_url", lambda _: BusyRedis())
        monkeypatch.setattr(worker, "worker_state", record_state)
        assert await worker.run_once() == {}
        assert states == []

    asyncio.run(verify())


def test_removal_probe_does_not_overlap_a_running_full_import(monkeypatch):
    async def verify() -> None:
        monkeypatch.setattr(worker, "get_settings", lambda: worker_settings(redis_url=""))
        await worker.local_import_lock.acquire()
        try:
            assert await worker.run_removal_once() == 0
        finally:
            worker.local_import_lock.release()

    asyncio.run(verify())
