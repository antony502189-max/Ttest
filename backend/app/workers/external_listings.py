from __future__ import annotations

import argparse
import asyncio
import logging
import signal
from uuid import uuid4

from redis.asyncio import from_url
from redis.exceptions import RedisError

from ..core.config import get_settings
from ..core.observability import configure_logging
from ..db.session import SessionLocal, engine
from ..external_sources import configured_sources
from ..services.external_import import run_source

logger = logging.getLogger(__name__)
local_import_lock = asyncio.Lock()


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
        if settings.redis_url:
            redis = from_url(settings.redis_url)
            try:
                acquired = await redis.set(
                    lock_key, token, ex=max(300, settings.external_import_request_timeout_seconds * 20), nx=True
                )
            except RedisError:
                logger.exception("external_import_lock_unavailable")
                return {}
            if not acquired:
                logger.info("external_import_already_running")
                return {}
        run_id = str(uuid4())
        for source in configured_sources():
            async with SessionLocal() as session:
                result[source.name] = await run_source(session, source, run_id)
        logger.info("external_import_finished", extra={"run_id": run_id, "sources": result})
        return result
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
    while not stopping.is_set():
        if not first_iteration or get_settings().external_import_run_on_start:
            try:
                await run_once()
            except Exception:
                logger.exception("external_import_iteration_failed")
        first_iteration = False
        try:
            await asyncio.wait_for(stopping.wait(), timeout=get_settings().external_import_interval_seconds)
        except TimeoutError:
            pass
    await engine.dispose()


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()
    asyncio.run(run_once() if args.once else loop())


if __name__ == "__main__":
    main()
