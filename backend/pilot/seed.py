"""Prepare the separately authorized <=20 public records without model IO."""
import asyncio
import json
from pathlib import Path


async def main():
    from app.db.session import SessionLocal, engine
    from app.services.ai_erasure_journal import configured_journal
    from demo.seed_state import seed_catalog
    from pilot.budget import PilotBudget
    from pilot.entry import require_pilot
    require_pilot()
    try:
        value = await seed_catalog(engine, SessionLocal, json.loads(Path("/demo-input/catalog.json").read_bytes()),
            Path("/demo-state"), configured_journal, budget_factory=PilotBudget)
        print(json.dumps(value))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
