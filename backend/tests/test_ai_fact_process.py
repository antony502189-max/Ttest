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


def premature_exit_factory():
    raise SystemExit(0)


class ReducibleFactory:
    def __call__(self):
        return failing_factory()

    def __reduce__(self):
        raise AssertionError("must never serialize a callable object in the parent")


@pytest.mark.parametrize("args", [[], ([],), ("x" * 8193,), ("x" * 8192,) * 5,
    (2**63,), (-(2**63) - 1,), (float("nan"),), (float("inf"),), tuple(range(17)), ("\ud800",)])
def test_non_scalar_or_oversized_launch_arguments_are_refused(args):
    with pytest.raises(ValueError, match="^SYNTHETIC_PROCESS_INPUT$"):
        run_isolated_tick(failing_factory, args, deadline_seconds=1)


@pytest.mark.parametrize("factory", [ReducibleFactory(), lambda: None, print])
def test_non_module_function_factory_is_refused_before_pickle(factory):
    with pytest.raises(ValueError, match="^SYNTHETIC_PROCESS_INPUT$"):
        run_isolated_tick(factory, (), deadline_seconds=1)


def test_nested_factory_is_refused_before_pickle():
    def nested():
        return failing_factory()
    with pytest.raises(ValueError, match="^SYNTHETIC_PROCESS_INPUT$"):
        run_isolated_tick(nested, (), deadline_seconds=1)


def test_clean_exit_without_tick_result_is_not_committed():
    result = run_isolated_tick(premature_exit_factory, (), deadline_seconds=5)
    assert result.exitcode == 0 and result.outcome == "failed"


def test_start_time_is_part_of_deadline(monkeypatch):
    process_type = type(multiprocessing.get_context("spawn").Process())
    original_start = process_type.start
    original_join = process_type.join
    waits = []

    def slow_start(process):
        time.sleep(1.1)
        original_start(process)

    def record_join(process, timeout=None):
        waits.append(timeout)
        original_join(process, timeout)

    monkeypatch.setattr(process_type, "start", slow_start)
    monkeypatch.setattr(process_type, "join", record_join)
    started = time.monotonic()
    result = run_isolated_tick(blocked_factory, (), deadline_seconds=1)
    assert result.outcome == "deadline"
    assert waits[0] == 0  # startup already consumed the full deadline
    assert time.monotonic() - started < 3


def test_custom_pickle_arguments_are_rejected_before_parent_execution(tmp_path):
    marker = tmp_path / "pickle-executed-in-parent"

    class Payload:
        def __reduce__(self):
            marker.write_text("executed", encoding="utf-8")
            return (str, ("unsafe",))

    with pytest.raises(ValueError, match="SYNTHETIC_PROCESS_INPUT"):
        run_isolated_tick(failing_factory, (Payload(),), deadline_seconds=5)
    assert not marker.exists()


def test_parent_start_failure_is_redacted_and_handles_are_closed(monkeypatch):
    process_type = type(multiprocessing.get_context("spawn").Process())
    original_close = process_type.close
    closed = []

    def fail_start(process):
        raise RuntimeError("PRIVATE_DATABASE_URL")

    def checked_close(process):
        closed.append(True)
        original_close(process)

    monkeypatch.setattr(process_type, "start", fail_start)
    monkeypatch.setattr(process_type, "close", checked_close)
    with pytest.raises(RuntimeError, match="^SYNTHETIC_PROCESS_UNAVAILABLE$") as error:
        run_isolated_tick(failing_factory, (), deadline_seconds=1)
    assert error.value.__cause__ is None and closed == [True]


def test_failed_reap_does_not_repeat_its_full_budget(monkeypatch):
    from lab import ai_fact_process

    class Unreapable:
        pid = 123
        exitcode = None

        def __init__(self):
            self.waits = []
            self.kills = 0

        def start(self):
            pass

        def join(self, timeout):
            self.waits.append(timeout)

        def is_alive(self):
            return True

        def kill(self):
            self.kills += 1

        def close(self):
            raise AssertionError("cannot close a live process")

    process = Unreapable()
    context = multiprocessing.get_context("spawn")
    monkeypatch.setattr(context, "Process", lambda **kwargs: process)
    monkeypatch.setattr(ai_fact_process.multiprocessing, "get_context", lambda method: context)
    with pytest.raises(RuntimeError, match="^SYNTHETIC_CHILD_REAP_FAILED$"):
        run_isolated_tick(failing_factory, (), deadline_seconds=1, reap_seconds=2)
    assert len(process.waits) == 2 and process.kills == 1


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
