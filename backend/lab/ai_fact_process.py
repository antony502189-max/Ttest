"""Explicit finite process boundary for trusted, disposable synthetic factories.

No scheduling or activation. Spawn constructs engines/journals in the child;
the parent never receives private exceptions or treats exit as a durable receipt.
The deadline includes spawn/setup. Recovery always reads the existing journals.
"""

import asyncio
import math
import multiprocessing
import sys
from collections.abc import Callable
from dataclasses import dataclass
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from time import monotonic
from types import FunctionType, ModuleType
from typing import Protocol

from lab.ai_fact_supervisor import bounded


class FiniteSyntheticTick(Protocol):
    async def run_once(self) -> str: ...


@dataclass(frozen=True)
class ProcessTickResult:
    pid: int
    outcome: str
    exitcode: int


def _launch_input(factory: Callable[..., FiniteSyntheticTick], args: tuple) -> None:
    # Arbitrary pickle reducers run in Process.start(), in the controlling
    # parent, outside the child kill boundary. Do not accept objects/callables
    # with custom serialization, live engines or unbounded configuration trees.
    if (type(factory) is not FunctionType
            or any(type(value) is not str for value in (factory.__name__, factory.__qualname__, factory.__module__))
            or not factory.__name__.isidentifier() or factory.__qualname__ != factory.__name__
            or type(args) is not tuple or len(args) > 16):
        raise ValueError("SYNTHETIC_PROCESS_INPUT")
    module = sys.modules.get(factory.__module__)
    if type(module) is not ModuleType or vars(module).get(factory.__name__) is not factory:
        raise ValueError("SYNTHETIC_PROCESS_INPUT")
    size = 0
    for value in args:
        if type(value) is str:
            if len(value) > 8192:
                raise ValueError("SYNTHETIC_PROCESS_INPUT")
            try:
                size += len(value.encode("utf-8"))
            except UnicodeError:
                raise ValueError("SYNTHETIC_PROCESS_INPUT") from None
        elif type(value) is int:
            if not -(2**63) <= value < 2**63:
                raise ValueError("SYNTHETIC_PROCESS_INPUT")
        elif type(value) is float:
            if not math.isfinite(value):
                raise ValueError("SYNTHETIC_PROCESS_INPUT")
        elif value is not None and type(value) is not bool:
            raise ValueError("SYNTHETIC_PROCESS_INPUT")
    if size > 32_768:
        raise ValueError("SYNTHETIC_PROCESS_INPUT")


def _tick(factory: Callable[..., FiniteSyntheticTick], args: tuple, reply: Connection) -> None:
    try:
        outcome = asyncio.run(factory(*args).run_once())
        # A clean process exit alone proves nothing: SystemExit(0), os._exit(0)
        # or bootstrap failure may bypass run_once entirely. Send only a tiny
        # explicit protocol result after run_once and event-loop shutdown.
        reply.send_bytes({"committed": b"committed", "deferred": b"deferred"}.get(outcome, b"failed"))
    except Exception:  # noqa: BLE001 -- never disclose builder/configuration payloads.
        raise SystemExit(12) from None
    finally:
        reply.close()


def _reap(process: BaseProcess, seconds: int) -> None:
    try:
        if process.is_alive():
            process.kill()
            process.join(seconds)
        if process.is_alive():
            raise RuntimeError("SYNTHETIC_CHILD_REAP_FAILED")
    except Exception:  # noqa: BLE001 -- OS/startup errors must not disclose configuration.
        raise RuntimeError("SYNTHETIC_CHILD_REAP_FAILED") from None


def run_isolated_tick(factory: Callable[..., FiniteSyntheticTick], args: tuple, *,
                      deadline_seconds: int, reap_seconds: int = 5) -> ProcessTickResult:
    """Run one trusted synthetic supervisor; return only after confirmed child exit.

    Factory must be a module-level function; args are at most 16 plain scalar
    values (None/bool/int64/finite float/str), with <=32KiB total UTF-8 strings
    and <=8192 characters each. No custom pickle or live engine/session objects.
    Only the direct child is supported: factories must not launch descendants.
    A timeout leaves durable claims untouched for lease/fence recovery. Even a
    successful exit requires receipt inspection by the explicit caller.
    """
    bounded(deadline_seconds, 3600)
    bounded(reap_seconds, 30)
    _launch_input(factory, args)
    deadline = monotonic() + deadline_seconds
    try:
        context = multiprocessing.get_context("spawn")
        receive, send = context.Pipe(duplex=False)
    except Exception:  # noqa: BLE001 -- redact IPC setup failures as well.
        raise RuntimeError("SYNTHETIC_PROCESS_UNAVAILABLE") from None
    process = None
    try:
        try:
            process = context.Process(target=_tick, args=(factory, args, send), daemon=True)
            process.start()
            send.close()
            process.join(max(0, deadline - monotonic()))
            timed_out = process.is_alive() or monotonic() >= deadline
        except Exception:  # noqa: BLE001 -- parent serialization/start/join errors are also private.
            raise RuntimeError("SYNTHETIC_PROCESS_UNAVAILABLE") from None
        finally:
            # One cleanup budget, also on KeyboardInterrupt of this sync caller.
            if process is not None:
                _reap(process, reap_seconds)
        if process.pid is None or process.exitcode is None:
            raise RuntimeError("SYNTHETIC_CHILD_REAP_FAILED")
        outcome = "failed"
        if timed_out:
            outcome = "deadline"
        elif process.exitcode == 0:
            try:
                if receive.poll():
                    outcome = {b"committed": "committed", b"deferred": "deferred"}.get(receive.recv_bytes(16), "failed")
            except (EOFError, OSError):
                pass  # Includes clean exit without a protocol reply; no implicit acknowledgement.
        return ProcessTickResult(process.pid, outcome, process.exitcode)
    finally:
        receive.close()
        send.close()
        if process is not None and not process.is_alive():
            process.close()
