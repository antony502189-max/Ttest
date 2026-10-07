"""Bounded province bootstrap through the existing importer; read-only by default."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from redis.asyncio import from_url
from redis.exceptions import RedisError
from sqlalchemy import func, select

from ..core.config import get_settings
from ..db.session import SessionLocal
from ..external_sources import configured_sources
from ..models import ExternalImportScope, ExternalListingSource, Listing
from ..services.external_import import run_source
from ..services.external_scopes import SOURCE_TYPES, ScopeDefinition, validate_scope
from ..workers.external_listings import (
    _acquire_distributed_lock,
    _refresh_distributed_lock_if_owned,
    _release_distributed_lock,
)
from .audit_external_sources import audit_source
from .provision_external_spain import read_manifest

LOCK_KEY = "ttest:external-listings-import"


@asynccontextmanager
async def import_lease(*, worker_paused: bool):
    settings = get_settings()
    if not settings.redis_url:
        if not worker_paused:
            raise RuntimeError("Without Redis, --worker-paused must explicitly confirm all workers are stopped")
        yield
        return
    redis = from_url(settings.redis_url)
    token = str(uuid4())
    acquired = False
    parent = asyncio.current_task()
    lease_lost = False

    async def refresh():
        nonlocal lease_lost
        try:
            while True:
                await asyncio.sleep(30)
                if not await _refresh_distributed_lock_if_owned(redis, LOCK_KEY, token, 21600):
                    raise RuntimeError("Bootstrap import lease was lost")
        except asyncio.CancelledError:
            raise
        except (RedisError, RuntimeError, OSError):
            lease_lost = True
            if parent:
                parent.cancel()

    heartbeat = None
    try:
        acquired = await _acquire_distributed_lock(redis, LOCK_KEY, token, 21600)
        if not acquired:
            raise RuntimeError("Import/removal worker currently owns the distributed lease")
        heartbeat = asyncio.create_task(refresh())
        try:
            yield
        except asyncio.CancelledError:
            if lease_lost:
                raise RuntimeError("Bootstrap stopped after losing the distributed lease") from None
            raise
    finally:
        if heartbeat:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
        if acquired:
            await _release_distributed_lock(redis, LOCK_KEY, token)
        await redis.aclose()


async def canonical_totals(session) -> dict:
    active = (Listing.is_external.is_(True), Listing.status == "published", Listing.deleted_at.is_(None))
    grouped = (
        await session.execute(
            select(Listing.rental_mode, Listing.room_type, func.count(Listing.id))
            .where(*active)
            .group_by(Listing.rental_mode, Listing.room_type)
        )
    ).all()
    sources = (
        await session.execute(
            select(Listing.primary_source, func.count(Listing.id)).where(*active).group_by(Listing.primary_source)
        )
    ).all()
    # Source coverage is DISTINCT canonical IDs per province. A canonical can
    # have multiple providers; these coverage counts must not be summed.
    provinces = (
        await session.execute(
            select(ExternalListingSource.scope_key, func.count(func.distinct(Listing.id)))
            .join(Listing, Listing.id == ExternalListingSource.canonical_listing_id)
            .where(*active, ExternalListingSource.current_status == "active")
            .group_by(ExternalListingSource.scope_key)
        )
    ).all()
    await session.commit()
    return {
        "total": sum(row[2] for row in grouped),
        "by_mode": {mode: sum(row[2] for row in grouped if row[0] == mode) for mode in ("long", "holiday")},
        "by_mode_property": [{"mode": row[0], "property": row[1], "count": row[2]} for row in grouped],
        "by_primary_source": dict(sources),
        "by_scope_distinct_canonicals": dict(provinces),
    }


def save_checkpoint(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def effective_budgets(max_pages: int, max_details: int) -> list[tuple[int, int]]:
    return list(
        dict.fromkeys(
            (min(pages, max_pages), min(details, max_details))
            for pages, details in ((1, 25), (5, 100), (max_pages, max_details))
        )
    )


def inventory_objective(totals: dict, args: argparse.Namespace) -> dict:
    modes = totals["by_mode"]
    total_met = totals["total"] >= args.target_total
    holiday_met = modes["holiday"] >= args.target_holiday_min
    return {
        "total": totals["total"],
        "long": modes["long"],
        "holiday": modes["holiday"],
        "target_total": args.target_total,
        "target_holiday_min": args.target_holiday_min,
        "total_target_satisfied": total_met,
        "holiday_min_satisfied": holiday_met,
        "satisfied": total_met and holiday_met,
    }


async def execute(args: argparse.Namespace) -> dict:
    if not args.apply:
        if not args.manifest:
            raise ValueError("Read-only audit requires a validated --manifest; no DB access is needed")
        definitions = read_manifest(args.manifest)
        report = []
        for definition in definitions:
            source = SOURCE_TYPES[definition.source_name]()
            source.scope_key, source.discovery_urls = definition.scope_key, definition.discovery_urls
            report.append(
                asdict(
                    await audit_source(
                        source,
                        max_pages=args.max_pages,
                        max_details=args.max_details,
                        source_timeout=args.source_timeout,
                        detail_timeout=30,
                    )
                )
            )
        return {"dry_run": True, "sources": report}
    settings = get_settings()
    if not settings.external_import_enabled or not settings.external_import_nationwide_enabled:
        raise RuntimeError("Apply requires both existing external import and nationwide gates to be enabled")
    adapters = configured_sources()
    enabled_names = {source.name for source in adapters}
    for source in adapters:
        await source.close()
    async with import_lease(worker_paused=args.worker_paused), SessionLocal() as session:
        rows = list(
            (
                await session.scalars(
                    select(ExternalImportScope)
                    .where(ExternalImportScope.enabled.is_(True))
                    .order_by(ExternalImportScope.scope_key, ExternalImportScope.source_name)
                )
            ).all()
        )
        tasks = [
            (
                row.id,
                validate_scope(ScopeDefinition(row.source_name, row.scope_key, tuple(row.discovery_urls))),
                row.interval_seconds,
            )
            for row in rows
        ]
        await session.commit()
        if not tasks:
            raise RuntimeError(
                "No enabled province scopes; provision and explicitly enable a controlled manifest first"
            )
        if any(value.source_name not in enabled_names for _, value, _ in tasks):
            raise RuntimeError("Enabled scope references an adapter not enabled in current source configuration")
        budgets = effective_budgets(args.max_pages, args.max_details)
        config = hashlib.sha256(
            json.dumps(
                {
                    "tasks": [(str(row_id), asdict(value)) for row_id, value, _ in tasks],
                    "max_pages": args.max_pages,
                    "max_details": args.max_details,
                    "effective_budgets": budgets,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        state: dict[str, Any] = {"configuration": config, "completed": [], "run_id": str(uuid4())}
        if args.checkpoint.exists() and not args.restart:
            state = json.loads(args.checkpoint.read_text(encoding="utf-8"))
            if state["configuration"] != config:
                raise ValueError("Scope configuration changed; use a new checkpoint or --restart")
        results: list[dict[str, Any]] = []
        total = await canonical_totals(session)
        # Breadth first: every supported province receives a small sample
        # before productive scopes are revisited with deeper budgets.
        for round_index, (pages, details) in enumerate(budgets):
            for row_id, definition, interval in tasks:
                key = f"{round_index}:{row_id}"
                if key in state["completed"]:
                    continue
                objective = inventory_objective(total, args)
                if objective["satisfied"] or len(results) >= args.max_scopes:
                    save_checkpoint(args.checkpoint, state)
                    return {
                        "dry_run": False,
                        "stop": "inventory_target_reached" if objective["satisfied"] else "scope_budget_reached",
                        "objective": objective,
                        "totals": total,
                        "results": results,
                    }
                source = SOURCE_TYPES[definition.source_name]()
                source.scope_key, source.discovery_urls = definition.scope_key, definition.discovery_urls
                source.max_discovery_pages = pages
                # Existing importer validates discovery and provider backoff.
                try:
                    outcome = await run_source(session, source, state["run_id"], max_details=details)
                finally:
                    await source.close()
                row = await session.get(ExternalImportScope, row_id)
                if row:
                    row.last_run_at, row.last_result = datetime.now(UTC), outcome.result
                    row.next_run_at = row.last_run_at + timedelta(
                        seconds=interval if outcome.result == "success" else 3600
                    )
                    await session.commit()
                entry = {
                    "source": source.name,
                    "scope": source.scope_key,
                    "round": round_index + 1,
                    "result": outcome.result,
                    "counters": dict(outcome),
                }
                results.append(entry)
                print(json.dumps(entry, ensure_ascii=False), flush=True)
                total = await canonical_totals(session)
                state["completed"].append(key)
                save_checkpoint(args.checkpoint, state)
        objective = inventory_objective(total, args)
        return {
            "dry_run": False,
            "stop": "inventory_target_reached" if objective["satisfied"] else "reviewed_scope_rounds_exhausted",
            "objective": objective,
            "totals": total,
            "results": results,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--worker-paused", action="store_true")
    parser.add_argument("--target-total", "--target", dest="target_total", type=int, default=2500)
    parser.add_argument("--target-holiday-min", type=int, default=500)
    parser.add_argument("--max-pages", type=int, default=30)
    parser.add_argument("--max-details", type=int, default=500)
    parser.add_argument("--max-scopes", type=int, default=156)
    parser.add_argument("--source-timeout", type=int, default=120)
    parser.add_argument("--checkpoint", type=Path, default=Path("var/external-spain-checkpoint.json"))
    parser.add_argument("--restart", action="store_true")
    args = parser.parse_args(argv)
    if not (
        1 <= args.target_total <= 10000
        and 0 <= args.target_holiday_min <= 10000
        and 1 <= args.max_pages <= 300
        and 1 <= args.max_details <= 1000
        and 1 <= args.max_scopes <= 1404
        and 15 <= args.source_timeout <= 180
    ):
        parser.error("Invalid bounded target, page/detail/scope or timeout budget")
    # A dry run samples, never fetches 500 details per province by default.
    if not args.apply:
        args.max_details = min(args.max_details, 5)
    report = asyncio.run(execute(args))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["dry_run"] or report["objective"]["satisfied"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
