from __future__ import annotations

import argparse
import asyncio
import json

from ..core.config import get_settings
from ..db.session import SessionLocal
from ..services.duplicate_cleanup import backfill_active_listing_hashes, deduplicate_active_listings


async def run(*, apply: bool) -> dict:
    get_settings().validate_runtime()
    async with SessionLocal() as session:
        backfilled = await backfill_active_listing_hashes(session) if apply else 0
        report = await deduplicate_active_listings(session, apply=apply)
        return {"mode": "apply" if apply else "dry-run", "hashesBackfilled": backfilled, **report}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detect duplicate active listings from photo galleries and optionally close duplicates."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Close detected duplicates. Without this flag the command is read-only.",
    )
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
