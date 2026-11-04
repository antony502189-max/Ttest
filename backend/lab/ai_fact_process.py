"""Explicit finite process boundary for trusted, disposable synthetic factories.

No scheduling or activation. Spawn constructs engines/journals in the child;
the parent never receives private exceptions or treats exit as a durable receipt.
The deadline includes spawn/setup. Recovery always reads the existing journals.
"""

import asyncio
import multiprocessing
from collections.abc import Callable
from dataclasses import dataclass

from lab.ai_fact_supervisor import SyntheticFactSupervisor, bounded


@dataclass(frozen=True)
class ProcessTickResult:
    pid: int
    outcome: str
    exitcode: int


def _tick(factory: Callable[..., SyntheticFactSupervisor], args: tuple) -> None:
    try:
        outcome = asyncio.run(factory(*args).run_once())
    except Exception:  # noqa: BLE001 -- never disclose builder/configuration payloads.
        raise SystemExit(12) from None
    raise SystemExit({"committed": 0, "deferred": 10}.get(outcome, 11))


def run_isolated_tick(factory: Callable[..., SyntheticFactSupervisor], args: tuple, *,
                      deadline_seconds: int, reap_seconds: int = 5) -> ProcessTickResult:
    """Run one trusted synthetic supervisor in a fresh child and always reap it.

    Factory and arguments must be spawn-pickleable, with no live engine/session.
    Only the direct child is supported: factories must not launch descendants.
    A timeout leaves durable claims untouched for lease/fence recovery. Even a
    successful exit requires receipt inspection by the explicit caller.
    """
    bounded(deadline_seconds, 3600)
    bounded(reap_seconds, 30)
    process = multiprocessing.get_context("spawn").Process(target=_tick, args=(factory, args), daemon=True)
    try:
        process.start()
        process.join(deadline_seconds)
        timed_out = process.is_alive()
        if timed_out:
            process.kill()
            process.join(reap_seconds)
        if process.is_alive():
            raise RuntimeError("SYNTHETIC_CHILD_REAP_FAILED")
        if process.pid is None or process.exitcode is None:
            raise RuntimeError("SYNTHETIC_CHILD_REAP_FAILED")
        outcome = "deadline" if timed_out else {0: "committed", 10: "deferred"}.get(process.exitcode, "failed")
        return ProcessTickResult(process.pid, outcome, process.exitcode)
    finally:
        # Includes interruption of the controlling caller, not only deadline.
        if process.is_alive():
            process.kill()
            process.join(reap_seconds)
        if process.is_alive():
            raise RuntimeError("SYNTHETIC_CHILD_REAP_FAILED")
        process.close()
