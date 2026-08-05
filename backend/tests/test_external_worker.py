from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.workers import external_listings as worker


class BusyRedis:
    async def set(self, *args, **kwargs) -> bool:
        return False

    async def get(self, *args, **kwargs):
        return None

    async def eval(self, *args, **kwargs) -> int:
        return 0

    async def aclose(self) -> None:
        return None


def worker_settings(**overrides):
    values = {
        "external_import_enabled": True,
        "external_removal_check_enabled": True,
        "external_import_interval_seconds": 7200,
        "external_import_min_healthy_sources": 1,
        "external_removal_check_interval_seconds": 900,
        "external_import_run_on_start": True,
        "external_worker_stale_after_seconds": 300,
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
        assert "useful import" in states[-1]["error"]

    asyncio.run(verify())


def test_worker_fails_when_only_two_of_three_required_sources_are_useful(monkeypatch):
    class Source:
        def __init__(self, name: str):
            self.name = name

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

        async def source_run(_session, source, _run_id):
            useful = source.name in {"Fotocasa", "Pisos"}
            values = {
                "discovered_urls": 1 if useful else 0,
                "fetched_details": 1 if useful else 0,
                "accepted_rooms": 1 if useful else 0,
            }
            return type(
                "Counters",
                (dict,),
                {"result": "success" if useful else "partial"},
            )(values)

        monkeypatch.setattr(
            worker,
            "get_settings",
            lambda: worker_settings(redis_url="", external_import_min_healthy_sources=3),
        )
        monkeypatch.setattr(
            worker,
            "configured_sources",
            lambda: [Source("Fotocasa"), Source("Pisos"), Source("ThinkSpain")],
        )
        monkeypatch.setattr(worker, "SessionLocal", EmptySession)
        monkeypatch.setattr(worker, "run_source", source_run)
        monkeypatch.setattr(worker, "worker_state", record_state)

        await worker.run_once()
        assert states[-1]["health"] == "failed"
        assert states[-1]["error"] == "Only 2 external sources completed a useful import; 3 required"

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

        monkeypatch.setattr(
            worker,
            "get_settings",
            lambda: worker_settings(external_removal_check_enabled=False, redis_url=""),
        )
        monkeypatch.setattr(worker, "run_once", run)
        monkeypatch.setattr(worker.asyncio, "Event", ControlledEvent)
        monkeypatch.setattr(worker.asyncio, "get_running_loop", SignalLoop)
        with pytest.raises(StopLoop):
            await worker.loop()
        assert calls == ["full"]

    asyncio.run(verify())


def test_release_does_not_delete_a_lock_owned_by_another_worker():
    class Redis:
        def __init__(self):
            self.value = "new-owner"

        async def eval(self, _script, _keys, _key, token):
            if self.value == token:
                self.value = None
                return 1
            return 0

    async def verify() -> None:
        redis = Redis()
        await worker._release_distributed_lock(redis, "lock", "old-owner")
        assert redis.value == "new-owner"

    asyncio.run(verify())


def test_stale_recovery_cannot_delete_a_reacquired_lock(monkeypatch):
    class Redis:
        def __init__(self):
            self.value = b"old-owner"

        async def get(self, _key):
            return self.value

        async def eval(self, _script, _keys, _key, token):
            # Simulate expiry and acquisition by a new worker between GET and EVAL.
            self.value = b"new-owner"
            if self.value == token.encode():
                self.value = None
                return 1
            return 0

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args):
            return SimpleNamespace(
                health="running",
                heartbeat_at=datetime.now(UTC) - timedelta(hours=3),
                last_run_id="old-owner",
            )

    async def verify() -> None:
        redis = Redis()
        monkeypatch.setattr(worker, "SessionLocal", Session)
        recovered = await worker._recover_stale_distributed_lock(redis, "lock", 60)
        assert recovered is False
        assert redis.value == b"new-owner"

    asyncio.run(verify())


def test_idle_wait_refreshes_heartbeat_before_the_stale_deadline(monkeypatch):
    async def verify() -> None:
        heartbeats: list[dict] = []

        async def record_state(**kwargs):
            heartbeats.append(kwargs)
            return SimpleNamespace()

        monkeypatch.setattr(worker, "get_settings", lambda: worker_settings(redis_url=""))
        monkeypatch.setattr(worker, "worker_state", record_state)
        await worker._wait_with_idle_heartbeat(asyncio.Event(), 0.045, heartbeat_interval=0.01)
        assert len(heartbeats) >= 3
        assert all(state == {} for state in heartbeats)

    asyncio.run(verify())


def test_idle_replica_does_not_refresh_heartbeat_while_import_lock_is_owned(monkeypatch):
    class LockedRedis:
        async def get(self, _key):
            return b"active-worker"

        async def aclose(self) -> None:
            return None

    async def verify() -> None:
        heartbeats: list[dict] = []

        async def record_state(**kwargs):
            heartbeats.append(kwargs)
            return SimpleNamespace()

        monkeypatch.setattr(worker, "get_settings", lambda: worker_settings())
        monkeypatch.setattr(worker, "from_url", lambda _url: LockedRedis())
        monkeypatch.setattr(worker, "worker_state", record_state)
        await worker._wait_with_idle_heartbeat(asyncio.Event(), 0.035, heartbeat_interval=0.01)
        assert heartbeats == []

    asyncio.run(verify())
