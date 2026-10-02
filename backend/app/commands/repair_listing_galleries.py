from __future__ import annotations

import argparse
import asyncio
import json

from ..core.config import get_settings
from ..db.session import SessionLocal
from ..services.listing_gallery_integrity import repair_legacy_internal_galleries


async def run(*, apply: bool) -> dict:
    get_settings().validate_runtime()
    async with SessionLocal() as session:
        return await repair_legacy_internal_galleries(session, apply=apply)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audit legacy internal listings with fewer than the required photos "
            "and optionally restore only unambiguous truncated galleries."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply unambiguous repairs. Without this flag the command is read-only.",
    )
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(apply=args.apply)), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
