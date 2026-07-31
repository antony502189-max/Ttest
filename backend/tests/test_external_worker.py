from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

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


def test_all_failed_sources_mark_the_worker_unhealthy(monkeypatch):
    class FailedSource:
        name = "Idealista"

    async def verify() -> None:
        states: list[dict] = []

        async def record_state(**kwargs):
            states.append(kwargs)
            return SimpleNamespace()

        class EmptySession:
            async def __aenter__(self):
                return object()

            async def __aexit__(self, *args):
                return None

        async def failed_run(*args, **kwargs):
            counters = {"failed": 1}
            counters = type("Counters", (dict,), {"result": "failed"})(counters)
            return counters

        monkeypatch.setattr(worker, "get_settings", lambda: worker_settings(redis_url=""))
        monkeypatch.setattr(worker, "configured_sources", lambda: [FailedSource()])
        monkeypatch.setattr(worker, "SessionLocal", EmptySession)
        monkeypatch.setattr(worker, "run_source", failed_run)
        monkeypatch.setattr(worker, "worker_state", record_state)

        await worker.run_once()
        assert states[-1]["health"] == "failed"
        assert "successful import" in states[-1]["error"]

    asyncio.run(verify())


def test_loop_runs_full_sync_on_start_before_waiting_for_the_interval(monkeypatch):
    class StopLoop(Exception):
        pass

    class ControlledEvent:
        def is_set(self) -> bool:
            return False

        def set(self) -> None:
            return None

        async def wait(self) -> None:
            raise StopLoop()

    class SignalLoop:
        def add_signal_handler(self, *args) -> None:
            return None

    async def verify() -> None:
        calls: list[str] = []

        async def run() -> dict:
            calls.append("full")
            return {}

        monkeypatch.setattr(worker, "get_settings", lambda: worker_settings(external_removal_check_enabled=False))
        monkeypatch.setattr(worker, "run_once", run)
        monkeypatch.setattr(worker.asyncio, "Event", ControlledEvent)
        monkeypatch.setattr(worker.asyncio, "get_running_loop", SignalLoop)
        with pytest.raises(StopLoop):
            await worker.loop()
        assert calls == ["full"]

    asyncio.run(verify())
