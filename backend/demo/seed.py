"""Explicit private-demo CLI; resumable state machine is in seed_state."""
import asyncio
import json
from pathlib import Path

from demo.seed_state import seed_catalog, verify_completed  # noqa: F401 - factory compatibility


async def seed():
    from app.db.session import SessionLocal, engine
    from app.services.ai_erasure_journal import configured_journal
    from demo.entry import require_demo
    require_demo()
    try:
        snapshot = json.loads(Path("/demo-input/catalog.json").read_bytes())
        print(json.dumps(await seed_catalog(engine, SessionLocal, snapshot, Path("/demo-state"), configured_journal)))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
