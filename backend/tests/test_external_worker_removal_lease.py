from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from redis.exceptions import RedisError

from app.workers import external_listings as worker


def test_effective_production_habitaclia_is_checked_with_1800_second_lease(monkeypatch):
    from app import external_sources, habitaclia_source

    class Redis(RenewableRedis):
        async def set(self, _key, token, *, ex, nx):
            assert ex == 1800 and nx is True
            self.value = token
            return True

        async def aclose(self):
            pass

    @asynccontextmanager
    async def session():
        yield object()

    async def verify():
        redis, checked, states = Redis(), [], []

        async def probe(_session, source, **kwargs):
            checked.append(source.name)
            kwargs["report"]["result"] = "success"

        async def heartbeat(**kwargs):
            states.append(kwargs)

        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setattr(habitaclia_source, "_installed", False)
        monkeypatch.setattr(external_sources, "configured_sources", list)
        habitaclia_source.install_habitaclia_source()
        monkeypatch.setattr(
            worker,
            "get_settings",
            lambda: SimpleNamespace(
                external_import_enabled=True,
                external_removal_check_enabled=True,
                external_removal_check_interval_seconds=21600,
                redis_url="redis://test",
                external_worker_stale_after_seconds=300,
            ),
        )
        monkeypatch.setattr(worker, "from_url", lambda _: redis)
        monkeypatch.setattr(worker, "SessionLocal", session)
        monkeypatch.setattr(worker, "run_removal_check", probe)
        monkeypatch.setattr(worker, "worker_state", heartbeat)
        assert await worker.run_removal_once() == 0
        assert checked == ["Habitaclia"]
        assert states and all(state == {} for state in states)
        assert redis.refreshes == 1 and redis.value == ""
        assert not worker.local_import_lock.locked()

    asyncio.run(verify())


def test_loop_keeps_removal_six_hours_apart_and_full_import_two_hours(monkeypatch):
    from app.core.config import Settings

    assert Settings(_env_file=None).external_removal_check_interval_seconds == 21600

    class StopLoop(Exception):
        pass

    class Clock:
        value = datetime(2026, 10, 7, tzinfo=UTC)

        @classmethod
        def now(cls, _tz):
            return cls.value

    class SignalLoop:
        def add_signal_handler(self, *_args):
            pass

    async def verify():
        calls, waits = [], []

        async def full():
            calls.append(("full", Clock.value))

        async def removal():
            calls.append(("removal", Clock.value))
            Clock.value += timedelta(seconds=300)  # Work duration must not shift cadence.
            return 0

        async def wait(_stop, timeout):
            waits.append(timeout)
            if len(waits) == 4:
                raise StopLoop()
            Clock.value += timedelta(seconds=timeout)

        monkeypatch.setattr(worker, "datetime", Clock)
        monkeypatch.setattr(worker.asyncio, "get_running_loop", SignalLoop)
        monkeypatch.setattr(
            worker,
            "get_settings",
            lambda: SimpleNamespace(
                external_import_run_on_start=True,
                external_import_interval_seconds=7200,
                external_removal_check_enabled=True,
                external_removal_check_interval_seconds=21600,
            ),
        )
        monkeypatch.setattr(worker, "run_once", full)
        monkeypatch.setattr(worker, "run_removal_once", removal)
        monkeypatch.setattr(worker, "_wait_with_idle_heartbeat", wait)
        with pytest.raises(StopLoop):
            await worker.loop()
        assert [name for name, _ in calls] == ["full", "removal", "full", "full", "full", "removal"]
        removal_times = [at for name, at in calls if name == "removal"]
        assert (removal_times[1] - removal_times[0]).total_seconds() == 21600
        assert waits[:3] == [6900, 7200, 7200]

    asyncio.run(verify())


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


def test_systemic_sweep_failure_marks_failed_and_releases_lock_even_if_client_close_fails(monkeypatch, caplog):
    class Source:
        name = "Idealista"

        async def close(self):
            raise RuntimeError("client close failed")

    @asynccontextmanager
    async def session():
        yield object()

    async def verify():
        states = []

        async def fail(_session, _source, **kwargs):
            raise RuntimeError("database unavailable")

        async def heartbeat(**kwargs):
            states.append(kwargs)

        monkeypatch.setattr(
            worker,
            "get_settings",
            lambda: SimpleNamespace(
                external_import_enabled=True,
                external_removal_check_enabled=True,
                redis_url="",
                external_worker_stale_after_seconds=300,
            ),
        )
        monkeypatch.setattr(worker.external_sources, "configured_sources", lambda: [Source()])
        monkeypatch.setattr(worker, "SessionLocal", session)
        monkeypatch.setattr(worker, "worker_state", heartbeat)
        monkeypatch.setattr(worker, "run_removal_check", fail)
        with pytest.raises(RuntimeError, match="database unavailable"):
            await worker.run_removal_once()
        assert states[-1]["health"] == "failed"
        assert not worker.local_import_lock.locked()
        assert '"result": "failed"' in caplog.text

    caplog.set_level("INFO")
    asyncio.run(verify())


def test_heartbeat_database_failure_cancels_sweep(monkeypatch):
    async def verify():
        cancelled = asyncio.Event()

        async def heartbeat(**_kwargs):
            raise RuntimeError("heartbeat database unavailable")

        async def slow():
            try:
                await asyncio.sleep(1)
            finally:
                cancelled.set()

        monkeypatch.setattr(worker, "worker_state", heartbeat)
        monkeypatch.setattr(worker, "get_settings", settings)
        with pytest.raises(RuntimeError, match="heartbeat database unavailable"):
            await worker._run_removal_probe_with_lease(
                slow(), redis=None, lock_key="lock", token="owner", lock_ttl=1800, heartbeat_interval=0.01
            )
        assert cancelled.is_set()

    asyncio.run(verify())


def test_removal_lease_connection_error_is_failed_not_busy(monkeypatch):
    class Redis:
        async def set(self, *args, **kwargs):
            raise RedisError("connection failed")
        async def eval(self, *args):
            return 0
        async def aclose(self):
            pass

    async def verify():
        states = []
        async def heartbeat(**kwargs):
            states.append(kwargs)
        monkeypatch.setattr(worker, "get_settings", lambda: SimpleNamespace(
            external_import_enabled=True, external_removal_check_enabled=True, redis_url="redis://test"))
        monkeypatch.setattr(worker, "from_url", lambda _: Redis())
        monkeypatch.setattr(worker, "worker_state", heartbeat)
        with pytest.raises(RedisError, match="connection failed"):
            await worker.run_removal_once()
        assert states[-1]["health"] == "failed"
        assert not worker.local_import_lock.locked()
    asyncio.run(verify())
