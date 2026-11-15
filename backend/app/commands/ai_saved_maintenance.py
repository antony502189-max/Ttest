"""One externally supervised bounded tick; SQL-only catalog and in-app alerts."""
import asyncio
import json
import os
from pathlib import Path
from uuid import UUID

from sqlalchemy import text

from ..db.session import SessionLocal, engine
from ..services.ai_saved_catalog import refresh_saved_catalog
from ..services.ai_saved_runtime import configured_saved_runtime, preflight_saved_runtime


async def main():
    try:
        async with asyncio.timeout(120):
            active = configured_saved_runtime(SessionLocal)
            if active is None:
                raise ValueError("AI_SAVED_CONFIGURATION_REQUIRED")
            await preflight_saved_runtime(active)
            path = Path(os.environ.get("AI_SAVED_COHORT_FILE", ""))
            if not path.is_absolute() or path.is_symlink() or path.stat().st_size > 20000:
                raise ValueError("AI_SAVED_EXPLICIT_COHORT_REQUIRED")
            payload = json.loads(path.read_text())
            if set(payload) != {"schema", "source_ids"} or payload["schema"] != "ai-saved-cohort.v1":
                raise ValueError("AI_SAVED_EXPLICIT_COHORT_REQUIRED")
            source_ids = tuple(UUID(value) for value in payload["source_ids"])
            async with SessionLocal() as lock:
                if not await lock.scalar(text("SELECT pg_try_advisory_lock(hashtextextended('ai-saved-maintenance.v1',0))")):
                    raise ValueError("AI_SAVED_MAINTENANCE_BUSY")
                try:
                    result = await refresh_saved_catalog(active.repo.pipeline, source_ids, include_current_authorities=True)
                    delivered = 0
                    for _ in range(4):
                        claim = await active.worker.claim()
                        if claim is None:
                            break
                        async with asyncio.timeout(15):
                            delivered += await active.worker.run(claim)
                    print(json.dumps(result | {"notifications_created": delivered, "email_sent": 0}))
                finally:
                    await lock.execute(text("SELECT pg_advisory_unlock(hashtextextended('ai-saved-maintenance.v1',0))"))
                    await lock.commit()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:  # noqa: BLE001 - redact source/criteria/database payloads
        print('{"status":"AI_SAVED_MAINTENANCE_UNAVAILABLE"}')
        raise SystemExit(1) from None
