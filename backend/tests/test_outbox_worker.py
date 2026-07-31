from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.commands import outbox_worker as worker


def test_worker_records_a_healthy_heartbeat_after_an_empty_batch(monkeypatch):
    class ControlledEvent:
        def __init__(self) -> None:
            self.stopping = False

        def is_set(self) -> bool:
            return self.stopping

        def set(self) -> None:
            self.stopping = True

        async def wait(self) -> None:
            self.stopping = True

    class SignalLoop:
        def add_signal_handler(self, *args) -> None:
            return None

    class EmptySession:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *args) -> None:
            return None

    async def verify() -> None:
        states: list[dict] = []

        async def record_state(**kwargs):
            states.append(kwargs)
            return SimpleNamespace()

        async def empty_batch(session) -> int:
            return 0

        monkeypatch.setattr(worker, "get_settings", lambda: SimpleNamespace(mail_worker_interval_seconds=1, validate_runtime=lambda: None))
        monkeypatch.setattr(worker, "SessionLocal", EmptySession)
        monkeypatch.setattr(worker, "worker_state", record_state)
        monkeypatch.setattr(worker, "deliver_pending_mail", empty_batch)
        monkeypatch.setattr(worker.asyncio, "Event", ControlledEvent)
        monkeypatch.setattr(worker.asyncio, "get_running_loop", SignalLoop)
        monkeypatch.setattr(worker, "engine", SimpleNamespace(dispose=lambda: asyncio.sleep(0)))

        await worker.run()
        assert [state["health"] for state in states] == ["running", "healthy"]

    asyncio.run(verify())
