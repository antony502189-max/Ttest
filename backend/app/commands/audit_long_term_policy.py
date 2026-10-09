"""Read-only inventory of existing listings against the long-term-only <= EUR 1000 policy.

This tool NEVER changes or deletes rows. Run against PostgreSQL only after
confirming the effective production database and a fresh backup. Its output
contains listing UUIDs, but no owner names, contacts, credentials or source URLs.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, text

from ..db.session import SessionLocal
from ..models import Listing
from ..services.rental_price_limit import MAX_LONG_TERM_RENT_EUR


def classify(mode: str, monthly_price: int | None) -> str:
    if mode != "long":
        return "holiday_or_unsupported"
    if monthly_price is None or monthly_price <= 0:
        return "missing_or_invalid_monthly_price"
    if monthly_price > MAX_LONG_TERM_RENT_EUR:
        return "long_term_above_ceiling"
    return "eligible_long_term"


async def inventory(max_rows: int) -> dict:
    records: list[dict] = []
    groups: Counter[str] = Counter()
    async with SessionLocal() as session:
        # Fail closed at the database: even a future accidental write must error.
        await session.execute(text("SET TRANSACTION READ ONLY"))
        rows = await session.stream(
            select(
                Listing.id, Listing.rental_mode, Listing.monthly_price,
                Listing.is_external, Listing.status, Listing.primary_source,
            ).where(Listing.deleted_at.is_(None)).order_by(Listing.id)
        )
        async for listing_id, mode, price, is_external, status, source in rows:
            if len(records) >= max_rows:
                raise RuntimeError(f"Listing inventory exceeds safe limit {max_rows}; no report written")
            classification = classify(mode, price)
            origin = "imported" if is_external else "user_created"
            groups[f"{classification}|{origin}|{status}|{source or 'none'}"] += 1
            records.append({
                "id": str(listing_id),
                "classification": classification,
                "origin": origin,
                "status": status,
                "source": source,
                "rentalMode": mode,
                "monthlyPrice": price,
            })
        await session.rollback()
    candidates = [item for item in records if item["classification"] != "eligible_long_term"]
    canonical = json.dumps(candidates, sort_keys=True, separators=(",", ":")).encode()
    return {
        "schema": 1,
        "generatedAt": datetime.now(UTC).isoformat(),
        "policy": {"rentalMode": "long", "minMonthlyEur": 1, "maxMonthlyEur": MAX_LONG_TERM_RENT_EUR},
        "totalNonDeleted": len(records),
        "eligibleCount": len(records) - len(candidates),
        "ineligibleCount": len(candidates),
        "candidatesSha256": hashlib.sha256(canonical).hexdigest(),
        "counts": dict(sorted(groups.items())),
        "ineligibleCandidates": candidates,
        "operation": "READ_ONLY_NO_DELETE",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New local JSON path (created as mode 0600)")
    parser.add_argument("--max-rows", type=int, default=100_000)
    args = parser.parse_args()
    if args.max_rows < 1 or args.max_rows > 1_000_000:
        parser.error("max-rows must be 1..1000000")
    result = asyncio.run(inventory(args.max_rows))
    path = args.output.expanduser().resolve()
    # Never overwrite an existing manifest and never default to a shared folder.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    print(json.dumps({
        "manifest": str(path),
        "totalNonDeleted": result["totalNonDeleted"],
        "eligibleCount": result["eligibleCount"],
        "ineligibleCount": result["ineligibleCount"],
        "candidatesSha256": result["candidatesSha256"],
        "operation": "READ_ONLY_NO_DELETE",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
