from __future__ import annotations

import argparse
import asyncio
import logging
import signal
from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import uuid4

from redis.asyncio import from_url
from redis.exceptions import RedisError

from ..core.config import get_settings
from ..core.observability import configure_logging
from ..db.session import SessionLocal, engine
from ..external_sources import configured_sources, retired_source_names
from ..models import ExternalWorkerState
from ..services.external_import import completed_source_contract, retire_source_records, run_removal_check, run_source

logger = logging.getLogger(__name__)
local_import_lock = asyncio.Lock()

_COMPARE_AND_DELETE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""

_COMPARE_AND_EXPIRE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
end
return 0
"""


async def _acquire_distributed_lock(redis, lock_key: str, token: str, ttl_seconds: int) -> bool:
    """Acquire the one shared import/removal lock without masking Redis failures."""
    try:
        return bool(await redis.set(lock_key, token, ex=ttl_seconds, nx=True))
    except RedisError:
        logger.exception("external_import_lock_unavailable")
        return False


async def _delete_distributed_lock_if_owned(redis, lock_key: str, token: str) -> bool:
    """Atomically delete a lock only while it still contains our token."""
    return bool(await redis.eval(_COMPARE_AND_DELETE_SCRIPT, 1, lock_key, token))


async def _refresh_distributed_lock_if_owned(redis, lock_key: str, token: str, ttl_seconds: int) -> bool:
    """Extend a lease only while it is still owned by this worker."""
    return bool(await redis.eval(_COMPARE_AND_EXPIRE_SCRIPT, 1, lock_key, token, str(ttl_seconds)))


async def _release_distributed_lock(redis, lock_key: str, token: str) -> None:
    try:
        await _delete_distributed_lock_if_owned(redis, lock_key, token)
    except RedisError:
        logger.warning("external_import_lock_release_failed")


async def _recover_stale_distributed_lock(redis, lock_key: str, max_age_seconds: int) -> bool:
    """Release an orphaned lock only when its recorded owner has stopped heartbeating."""
    try:
        token = await redis.get(lock_key)
        if not token:
            return False
        decoded_token = token.decode("utf-8") if isinstance(token, bytes) else str(token)
        async with SessionLocal() as session:
            state = await session.get(ExternalWorkerState, 1)
        if (
            not state
            or state.health != "running"
            or not state.heartbeat_at
            or state.last_run_id != decoded_token
            or state.heartbeat_at >= datetime.now(UTC) - timedelta(seconds=max_age_seconds)
        ):
            return False
        # The lock may have expired and been acquired by another worker while
        # the database state was checked. Compare-and-delete prevents removing
        # that newer worker's token.
        return await _delete_distributed_lock_if_owned(redis, lock_key, decoded_token)
    except (RedisError, UnicodeDecodeError):
        logger.exception("external_import_stale_lock_recovery_failed")
        return False


async def _heartbeat_while_running(stopping: asyncio.Event, run_id: str) -> None:
    """Keep the health state fresh while a source import is legitimately slow."""
    interval = min(60, max(15, get_settings().external_worker_stale_after_seconds // 3))
    while not stopping.is_set():
        try:
            await asyncio.wait_for(stopping.wait(), timeout=interval)
        except TimeoutError:
            try:
                await worker_state(run_id=run_id)
            except Exception:
                # A temporary database failure must not terminate the heartbeat
                # task and later mask the import result from the main task.
                logger.exception("external_import_heartbeat_failed", extra={"run_id": run_id})


async def _run_removal_probe_with_lease(
    operation,
    *,
    redis,
    lock_key: str,
    token: str,
    lock_ttl: int,
    heartbeat_interval: float | None = None,
):
    """Run a potentially slow removal probe while maintaining health and lock ownership."""
    interval = heartbeat_interval or min(60, max(15, get_settings().external_worker_stale_after_seconds // 3))
    task = asyncio.create_task(operation)

    async def maintain() -> None:
        try:
            await worker_state()
        except Exception:
            logger.exception("external_removal_heartbeat_failed")
        if redis is None:
            return
        try:
            refreshed = await _refresh_distributed_lock_if_owned(redis, lock_key, token, lock_ttl)
        except RedisError as exc:
            raise RuntimeError("external removal lock refresh failed") from exc
        if not refreshed:
            raise RuntimeError("external removal lock lost")

    try:
        while True:
            try:
                result = await asyncio.wait_for(asyncio.shield(task), timeout=interval)
            except TimeoutError:
                try:
                    await maintain()
                except Exception:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    raise
                continue
            await maintain()
            return result
    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


async def _wait_with_idle_heartbeat(
    stopping: asyncio.Event,
    timeout: float,
    *,
    heartbeat_interval: float | None = None,
) -> None:
    """Wait for the next scheduled job without letting the worker appear stale.

    An idle replica publishes a heartbeat only while the shared import lock is
    free. This keeps the normal single worker healthy without allowing a
    passive replica to hide a crashed lock owner.
    """
    if timeout <= 0 or stopping.is_set():
        return
    settings = get_settings()
    interval = heartbeat_interval or min(60, max(15, settings.external_worker_stale_after_seconds // 3))
    deadline = monotonic() + timeout
    redis = from_url(settings.redis_url) if settings.redis_url else None
    lock_key = "ttest:external-listings-import"

    async def publish_idle_heartbeat() -> None:
        try:
            if redis is not None and await redis.get(lock_key):
                return
            await worker_state()
        except RedisError:
            logger.exception("external_import_idle_lock_check_failed")
        except Exception:
            logger.exception("external_import_idle_heartbeat_failed")

    try:
        while not stopping.is_set():
            # Publish before sleeping so a coarse event loop cannot consume the
            # whole idle window before its first scheduled timer callback.
            await publish_idle_heartbeat()
            remaining = deadline - monotonic()
            if remaining <= 0:
                return
            try:
                await asyncio.wait_for(stopping.wait(), timeout=min(interval, remaining))
                return
            except TimeoutError:
                continue
    finally:
        if redis is not None:
            await redis.aclose()


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


def _successful_source_names(result: dict[str, dict[str, int]]) -> list[str]:
    return [
        name
        for name, counters in result.items()
        if getattr(counters, "result", "failed") == "success"
        and completed_source_contract(counters)
    ]


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
            acquired = await _acquire_distributed_lock(redis, lock_key, token, lock_ttl)
            if not acquired:
                if not await _recover_stale_distributed_lock(
                    redis,
                    lock_key,
                    settings.external_worker_stale_after_seconds,
                ):
                    return {}
                if not await _acquire_distributed_lock(redis, lock_key, token, lock_ttl):
                    return {}
        # Only the worker that holds the distributed lock may publish a
        # running state; otherwise a passive replica would overwrite the
        # heartbeat of the active worker.
        await worker_state(health="running", run_id=run_id)
        heartbeat_stop = asyncio.Event()
        heartbeat_task = asyncio.create_task(_heartbeat_while_running(heartbeat_stop, run_id))
        sources = configured_sources()
        retired_names = retired_source_names({source.name.casefold() for source in sources})
        if retired_names:
            async with SessionLocal() as session:
                retired = await retire_source_records(session, retired_names)
            if retired:
                logger.info("external_import_retired_sources", extra={"run_id": run_id, "closed": retired})
        for source in sources:
            async with SessionLocal() as session:
                result[source.name] = await run_source(session, source, run_id)
            await worker_state(health="running", run_id=run_id)
        logger.info("external_import_finished", extra={"run_id": run_id, "sources": result})
        successful_sources = _successful_source_names(result)
        required_sources = settings.external_import_min_healthy_sources
        if len(successful_sources) < required_sources:
            failure_summary = (
                f"Only {len(successful_sources)} external sources completed a useful import; "
                f"{required_sources} required"
            )
            logger.error(
                "external_import_insufficient_healthy_sources",
                extra={
                    "run_id": run_id,
                    "successful_sources": successful_sources,
                    "required_sources": required_sources,
                    "sources": result,
                },
            )
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
    lock_ttl = max(1_800, settings.external_removal_check_interval_seconds * 2)
    try:
        if settings.redis_url:
            redis = from_url(settings.redis_url)
            if not await _acquire_distributed_lock(redis, lock_key, token, lock_ttl):
                return 0
        # The removal cycle owns the shared lease, so it is responsible for
        # keeping the heartbeat fresh while remote state checks are in flight.
        await worker_state()
        archived = 0
        for source in configured_sources():
            async with SessionLocal() as session:
                archived += await _run_removal_probe_with_lease(
                    run_removal_check(session, source),
                    redis=redis,
                    lock_key=lock_key,
                    token=token,
                    lock_ttl=lock_ttl,
                )
                await session.commit()
            # A removal probe is not a full import run. It still supplies a
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
        await _wait_with_idle_heartbeat(stopping, timeout)
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
                max_age = get_settings().external_worker_stale_after_seconds
                if state.heartbeat_at < datetime.now(UTC) - timedelta(seconds=max_age):
                    raise SystemExit(1)

        asyncio.run(check())
    else:
        asyncio.run(run_once() if args.once else loop())


if __name__ == "__main__":
    main()
