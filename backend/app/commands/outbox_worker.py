from __future__ import annotations

import asyncio
import logging
import signal

from ..core.config import get_settings
from ..core.observability import configure_logging
from ..db.session import SessionLocal, engine
from ..services.mail import deliver_pending_mail

logger = logging.getLogger(__name__)


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
        while not stopping.is_set():
            try:
                async with SessionLocal() as session:
                    delivered = await deliver_pending_mail(session)
                if delivered:
                    logger.info("mail_batch_delivered", extra={"delivered": delivered})
            except Exception:
                logger.exception("mail_worker_iteration_failed")
            try:
                await asyncio.wait_for(stopping.wait(), timeout=settings.mail_worker_interval_seconds)
            except TimeoutError:
                pass
    finally:
        await engine.dispose()
        logger.info("mail_worker_stopped")


if __name__ == "__main__":
    asyncio.run(run())
