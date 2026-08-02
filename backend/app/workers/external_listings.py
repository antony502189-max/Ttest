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


async def _acquire_distributed_lock(redis, lock_key: str, token: str, ttl_seconds: int) -> bool:
    """Acquire the one shared import/removal lock without masking Redis failures."""
    try:
        return bool(await redis.set(lock_key, token, ex=ttl_seconds, nx=True))
    except RedisError:
        logger.exception("external_import_lock_unavailable")
        return False


async def _release_distributed_lock(redis, lock_key: str, token: str) -> None:
    try:
        if await redis.get(lock_key) == token.encode():
            await redis.delete(lock_key)
    except RedisError:
        logger.warning("external_import_lock_release_failed")


async def _recover_stale_distributed_lock(redis, lock_key: str, max_age_seconds: int) -> bool:
    """Release an orphaned lock only when its recorded owner has stopped heartbeating."""
    try:
        token = await redis.get(lock_key)
        if not token:
            return False
        async with SessionLocal() as session:
            state = await session.get(ExternalWorkerState, 1)
        if (
            not state
            or state.health != "running"
            or not state.heartbeat_at
            or state.last_run_id != token.decode()
            or state.heartbeat_at >= datetime.now(UTC) - timedelta(seconds=max_age_seconds)
        ):
            return False
        return bool(await redis.delete(lock_key))
    except (RedisError, UnicodeDecodeError):
        logger.exception("external_import_stale_lock_recovery_failed")
        return False


async def _heartbeat_while_running(stopping: asyncio.Event, run_id: str) -> None:
    """Keep the health state fresh while a source import is legitimately slow."""
    interval = min(60, max(15, get_settings().external_import_interval_seconds // 2))
    while not stopping.is_set():
        try:
            await asyncio.wait_for(stopping.wait(), timeout=interval)
        except TimeoutError:
            await worker_state(run_id=run_id)


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
    run_id = str(uuid4())
    token = run_id
    lock_key = "ttest:external-listings-import"
    result: dict[str, dict[str, int]] = {}
    heartbeat_stop: asyncio.Event | None = None
    heartbeat_task: asyncio.Task[None] | None = None
    try:
        if settings.redis_url:
            redis = from_url(settings.redis_url)
            lock_ttl = max(21_600, settings.external_import_interval_seconds * 2)
            acquired = await _acquire_distributed_lock(
                redis,
                lock_key,
                token,
                lock_ttl,
            )
            if not acquired:
                max_age = max(120, settings.external_import_interval_seconds + 120)
                if not await _recover_stale_distributed_lock(redis, lock_key, max_age):
                    return {}
                if not await _acquire_distributed_lock(redis, lock_key, token, lock_ttl):
                    return {}
        # Only the worker that holds the distributed lock may publish a
        # running state; otherwise a passive replica would overwrite the
        # heartbeat of the active worker.
        await worker_state(health="running", run_id=run_id)
        heartbeat_stop = asyncio.Event()
        heartbeat_task = asyncio.create_task(_heartbeat_while_running(heartbeat_stop, run_id))
        for source in configured_sources():
            async with SessionLocal() as session:
                result[source.name] = await run_source(session, source, run_id)
            await worker_state(health="running", run_id=run_id)
        logger.info("external_import_finished", extra={"run_id": run_id, "sources": result})
        successful_sources = [
            name for name, counters in result.items() if getattr(counters, "result", "failed") == "success"
        ]
        if not successful_sources:
            failure_summary = "No external source completed a successful import"
            logger.error("external_import_no_successful_sources", extra={"run_id": run_id, "sources": result})
            await worker_state(health="failed", error=failure_summary, run_id=run_id)
            return result
        await worker_state(health="healthy", run_id=run_id)
        return result
    except Exception as exc:
        await worker_state(health="failed", error=str(exc), run_id=run_id)
        raise
    finally:
        if heartbeat_stop and heartbeat_task:
            heartbeat_stop.set()
            await heartbeat_task
        if redis:
            try:
                await _release_distributed_lock(redis, lock_key, token)
            finally:
                await redis.aclose()
        local_import_lock.release()


async def run_removal_once() -> int:
    """Run lightweight checks under the same local and Redis lock as full syncs."""
    settings = get_settings()
    if not settings.external_import_enabled or not settings.external_removal_check_enabled:
        return 0
    if local_import_lock.locked():
        logger.info("external_removal_check_already_running")
        return 0
    await local_import_lock.acquire()
    redis = None
    token = str(uuid4())
    lock_key = "ttest:external-listings-import"
    try:
        if settings.redis_url:
            redis = from_url(settings.redis_url)
            if not await _acquire_distributed_lock(
                redis,
                lock_key,
                token,
                max(1_800, settings.external_removal_check_interval_seconds * 2),
            ):
                return 0
        archived = 0
        for source in configured_sources():
            async with SessionLocal() as session:
                archived += await run_removal_check(session, source)
                await session.commit()
            # A removal probe is not a full import run.  It still supplies a
            # heartbeat but must not change last_started_at/health to running.
            await worker_state()
        return archived
    finally:
        if redis:
            try:
                await _release_distributed_lock(redis, lock_key, token)
            finally:
                await redis.aclose()
        local_import_lock.release()


async def loop() -> None:
    stopping = asyncio.Event()
    event_loop = asyncio.get_running_loop()
    for name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, name):
            event_loop.add_signal_handler(getattr(signal, name), stopping.set)
    settings = get_settings()
    now = datetime.now(UTC)
    next_full_sync = now if settings.external_import_run_on_start else now + timedelta(
        seconds=settings.external_import_interval_seconds
    )
    next_removal_check = now if settings.external_removal_check_enabled else None
    while not stopping.is_set():
        now = datetime.now(UTC)
        if now >= next_full_sync:
            try:
                await run_once()
            except Exception:
                logger.exception("external_import_iteration_failed")
            next_full_sync = datetime.now(UTC) + timedelta(seconds=settings.external_import_interval_seconds)
        now = datetime.now(UTC)
        if next_removal_check is not None and now >= next_removal_check:
            try:
                await run_removal_once()
            except Exception:
                logger.exception("external_removal_check_failed")
            next_removal_check = datetime.now(UTC) + timedelta(seconds=settings.external_removal_check_interval_seconds)
        deadlines = [next_full_sync]
        if next_removal_check is not None:
            deadlines.append(next_removal_check)
        timeout = max(0.0, min((deadline - datetime.now(UTC)).total_seconds() for deadline in deadlines))
        try:
            await asyncio.wait_for(stopping.wait(), timeout=timeout)
        except TimeoutError:
            pass
    await engine.dispose()


def main() -> None:
    configure_logging()
    get_settings().validate_runtime()
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
