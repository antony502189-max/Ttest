from __future__ import annotations

import argparse
import asyncio
import logging
import signal
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from redis.asyncio import from_url
from redis.exceptions import RedisError

from ..core.config import get_settings
from ..core.observability import configure_logging
from ..db.session import SessionLocal, engine
from ..external_sources import configured_sources
from ..models import ExternalWorkerState
from ..services.external_import import run_removal_check, run_source

logger = logging.getLogger(__name__)
local_import_lock = asyncio.Lock()


async def worker_state(*, health: str | None = None, error: str | None = None, run_id: str | None = None) -> ExternalWorkerState:
    now = datetime.now(UTC)
    async with SessionLocal() as session:
        state = await session.get(ExternalWorkerState, 1)
        if not state:
            state = ExternalWorkerState(id=1)
            session.add(state)
        state.heartbeat_at = now
        if health:
            state.health = health
        if run_id:
            state.last_run_id = run_id
        if health == "running":
            state.last_started_at = now
        if health in {"healthy", "failed"}:
            state.last_finished_at = now
            state.next_run_at = now + timedelta(seconds=get_settings().external_import_interval_seconds)
        if health == "healthy":
            state.last_success_at = now
            state.last_error = None
        elif error:
            state.last_error = error
        await session.commit()
        return state


async def run_once() -> dict[str, dict[str, int]]:
    settings = get_settings()
    if not settings.external_import_enabled:
        return {}
    if local_import_lock.locked():
        logger.info("external_import_already_running")
        return {}
    await local_import_lock.acquire()
    redis = None
    token = str(uuid4())
    lock_key = "ttest:external-listings-import"
    result: dict[str, dict[str, int]] = {}
    try:
        run_id = str(uuid4())
        await worker_state(health="running", run_id=run_id)
        if settings.redis_url:
            redis = from_url(settings.redis_url)
            try:
                acquired = await redis.set(
                    # A full source run can download and normalize many public images.
                    # Use a TTL longer than the permitted import window; deletion still
                    # verifies the unique token so one worker never removes another lock.
                    lock_key,
                    token,
                    ex=max(21_600, settings.external_import_interval_seconds * 2),
                    nx=True,
                )
            except RedisError:
                logger.exception("external_import_lock_unavailable")
                return {}
            if not acquired:
                logger.info("external_import_already_running")
                return {}
        for source in configured_sources():
            async with SessionLocal() as session:
                result[source.name] = await run_source(session, source, run_id)
            await worker_state(health="running", run_id=run_id)
        logger.info("external_import_finished", extra={"run_id": run_id, "sources": result})
        await worker_state(health="healthy", run_id=run_id)
        return result
    except Exception as exc:
        await worker_state(health="failed", error=str(exc), run_id=run_id if "run_id" in locals() else None)
        raise
    finally:
        if redis:
            try:
                if await redis.get(lock_key) == token.encode():
                    await redis.delete(lock_key)
            except RedisError:
                logger.warning("external_import_lock_release_failed")
            finally:
                await redis.aclose()
        local_import_lock.release()


async def loop() -> None:
    stopping = asyncio.Event()
    event_loop = asyncio.get_running_loop()
    for name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, name):
            event_loop.add_signal_handler(getattr(signal, name), stopping.set)
    first_iteration = True
    next_removal_check = datetime.now(UTC)
    while not stopping.is_set():
        if not first_iteration or get_settings().external_import_run_on_start:
            try:
                await run_once()
            except Exception:
                logger.exception("external_import_iteration_failed")
        first_iteration = False
        if get_settings().external_removal_check_enabled and datetime.now(UTC) >= next_removal_check:
            try:
                for source in configured_sources():
                    async with SessionLocal() as session:
                        await run_removal_check(session, source)
                        await session.commit()
                next_removal_check = datetime.now(UTC) + timedelta(seconds=get_settings().external_removal_check_interval_seconds)
            except Exception:
                logger.exception("external_removal_check_failed")
        try:
            await asyncio.wait_for(stopping.wait(), timeout=min(get_settings().external_import_interval_seconds, get_settings().external_removal_check_interval_seconds))
        except TimeoutError:
            pass
    await engine.dispose()


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--healthcheck", action="store_true")
    args = parser.parse_args()
    if args.healthcheck:
        async def check() -> None:
            async with SessionLocal() as session:
                state = await session.get(ExternalWorkerState, 1)
                if not state or state.health == "failed" or not state.heartbeat_at:
                    raise SystemExit(1)
                max_age = max(120, get_settings().external_import_interval_seconds + 120)
                if state.heartbeat_at < datetime.now(UTC) - timedelta(seconds=max_age):
                    raise SystemExit(1)
        asyncio.run(check())
    else:
        asyncio.run(run_once() if args.once else loop())


if __name__ == "__main__":
    main()
