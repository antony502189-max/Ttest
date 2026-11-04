"""Process boundary validation and cleanup when its controlling caller is interrupted."""

import multiprocessing
import time

import pytest

from lab.ai_fact_process import run_isolated_tick


def failing_factory():
    raise RuntimeError("PRIVATE_SYNTHETIC_FACTORY_ERROR")


def blocked_factory():
    time.sleep(60)
    raise AssertionError("must be killed")


@pytest.mark.parametrize("field,value", [("deadline_seconds", 0), ("deadline_seconds", True),
    ("deadline_seconds", 3601), ("reap_seconds", 0), ("reap_seconds", 31)])
def test_policy_rejects_unbounded_process_work(field, value):
    with pytest.raises(ValueError):
        run_isolated_tick(failing_factory, (), **({"deadline_seconds": 5} | {field: value}))


def test_child_factory_failure_is_redacted_and_reaped(capfd):
    result = run_isolated_tick(failing_factory, (), deadline_seconds=5)
    assert result.outcome == "failed" and result.exitcode == 12
    assert result.pid not in {p.pid for p in multiprocessing.active_children()}
    assert "PRIVATE_SYNTHETIC" not in str(capfd.readouterr())


def test_controller_interruption_kills_and_reaps_actual_child(monkeypatch):
    context = multiprocessing.get_context("spawn")
    process = context.Process()
    process_type = type(process)
    process.close()
    original_join, original_close = process_type.join, process_type.close
    joins, reaped = [], []

    def interrupted_join(child, timeout=None):
        joins.append(child.pid)
        if len(joins) == 1:
            original_join(child, 0.2)
            assert child.is_alive()
            raise KeyboardInterrupt
        return original_join(child, timeout)

    def checked_close(child):
        reaped.append((child.pid, child.is_alive(), child.exitcode))
        original_close(child)

    monkeypatch.setattr(process_type, "join", interrupted_join)
    monkeypatch.setattr(process_type, "close", checked_close)
    with pytest.raises(KeyboardInterrupt):
        run_isolated_tick(blocked_factory, (), deadline_seconds=5)
    assert len(joins) == 2 and len(reaped) == 1
    assert reaped[0][1] is False and reaped[0][2] is not None
    assert reaped[0][0] not in {p.pid for p in multiprocessing.active_children()}
