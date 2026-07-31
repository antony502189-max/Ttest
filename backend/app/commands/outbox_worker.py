from __future__ import annotations

import argparse
import asyncio
import logging
import signal
from datetime import UTC, datetime, timedelta

from ..core.config import get_settings
from ..core.observability import configure_logging
from ..db.session import SessionLocal, engine
from ..models import MailWorkerState
from ..services.mail import deliver_pending_mail

logger = logging.getLogger(__name__)


async def worker_state(*, health: str, error: str | None = None) -> MailWorkerState:
    now = datetime.now(UTC)
    async with SessionLocal() as session:
        state = await session.get(MailWorkerState, 1)
        if not state:
            state = MailWorkerState(id=1)
            session.add(state)
        state.health = health
        state.heartbeat_at = now
        if health == "healthy":
            state.last_success_at = now
            state.last_error = None
        elif error:
            state.last_error = error
        await session.commit()
        return state


async def run() -> None:
    configure_logging()
    settings = get_settings()
    settings.validate_runtime()
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    for name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, name):
            loop.add_signal_handler(getattr(signal, name), stopping.set)

    logger.info("mail_worker_started")
    try:
        await worker_state(health="running")
        while not stopping.is_set():
            try:
                async with SessionLocal() as session:
                    delivered = await deliver_pending_mail(session)
                await worker_state(health="healthy")
                if delivered:
                    logger.info("mail_batch_delivered", extra={"delivered": delivered})
            except Exception as exc:
                await worker_state(health="failed", error=type(exc).__name__)
                logger.exception("mail_worker_iteration_failed")
            try:
                await asyncio.wait_for(stopping.wait(), timeout=settings.mail_worker_interval_seconds)
            except TimeoutError:
                pass
    finally:
        await engine.dispose()
        logger.info("mail_worker_stopped")


def main() -> None:
    configure_logging()
    get_settings().validate_runtime()
    parser = argparse.ArgumentParser()
    parser.add_argument("--healthcheck", action="store_true")
    args = parser.parse_args()
    if not args.healthcheck:
        asyncio.run(run())
        return

    async def check() -> None:
        async with SessionLocal() as session:
            state = await session.get(MailWorkerState, 1)
            max_age = max(120, get_settings().mail_worker_interval_seconds * 3)
            if (
                not state
                or state.health == "failed"
                or not state.heartbeat_at
                or state.heartbeat_at < datetime.now(UTC) - timedelta(seconds=max_age)
            ):
                raise SystemExit(1)

    asyncio.run(check())


if __name__ == "__main__":
    main()
