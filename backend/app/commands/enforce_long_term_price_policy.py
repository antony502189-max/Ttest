"""Read-only catalog inventory and separately approved, recoverable maintenance.

No startup/deployment hook calls this module. Reports contain no contact data.
Each reviewed plan selects at most 500 rows; inventory enumerates all candidates.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import os
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy import delete, func, inspect, select, text

from ..core.config import get_settings
from ..db.session import SessionLocal
from ..models import AuditLog, Listing, ListingStatusHistory
from ..services.catalog import touch_catalog
from ..services.rental_policy import POLICY_VERSION, listing_eligibility

MAX_PLAN_ROWS = 500
PROTECTED_TABLES = {
    "favorites", "discarded_listings", "external_listing_sources", "message_threads", "messages",
    "reports", "listing_promotions", "homepage_hero_promotions", "notifications", "listing_restrictions",
}


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def seal(manifest: dict) -> dict:
    manifest = dict(manifest)
    manifest["digest"] = digest({k: v for k, v in manifest.items() if k != "digest"})
    return manifest


def snapshot_digest(manifest: dict) -> str:
    return digest({k: v for k, v in manifest.items() if k not in {"digest", "generated_at"}})


def verify_manifest(manifest: dict) -> None:
    if manifest.get("digest") != seal(manifest)["digest"] or manifest.get("policy_version") != POLICY_VERSION:
        raise ValueError("Manifest was altered or uses another rental policy")
    if manifest.get("plan_action") not in {"withdraw", "purge"} or not 1 <= manifest.get("plan_limit", 0) <= MAX_PLAN_ROWS:
        raise ValueError("Invalid manifest action or transaction limit")
    selected = manifest.get("selected_ids", [])
    if len(selected) > MAX_PLAN_ROWS or len(selected) != len(set(selected)):
        raise ValueError("Manifest exceeds the bounded transaction limit")
    known = {row["id"] for row in manifest["candidates"]}
    if not set(selected) <= known:
        raise ValueError("Manifest selects an unreviewed listing")


def hard_delete_exclusions(dependencies: dict) -> list[str]:
    # Unknown dependencies fail closed even if their FK says CASCADE. Only
    # listing-owned bookkeeping and image links can cascade in a purge.
    disposable = {"listing_images", "listing_room_details", "listing_status_history", "listing_views"}
    return sorted(name for name, count in dependencies.items() if count and (
        name in PROTECTED_TABLES or name not in disposable
    ))


async def relationship_graph(session) -> list[dict]:
    connection = await session.connection()

    def read(sync_connection):
        inspector = inspect(sync_connection)
        edges = []
        for table in sorted(inspector.get_table_names(schema="public")):
            for fk in inspector.get_foreign_keys(table, schema="public"):
                edges.append({"table": table, "columns": fk["constrained_columns"],
                    "parent": fk["referred_table"], "parent_columns": fk["referred_columns"],
                    "ondelete": fk.get("options", {}).get("ondelete", "NO ACTION")})
        return sorted(edges, key=lambda edge: (edge["table"], edge["columns"], edge["parent"]))

    return await connection.run_sync(read)


def relationship_paths(graph: list[dict]) -> list[list[dict]]:
    paths = []
    pending: list[tuple[str, list[dict]]] = [("listings", [])]
    while pending:
        parent, path = pending.pop()
        visited = {"listings", *(edge["table"] for edge in path)}
        for edge in graph:
            if edge["parent"] == parent and edge["table"] not in visited:
                next_path = [edge, *path]
                paths.append(next_path)
                pending.append((edge["table"], next_path))
    return paths


async def inventory(session, *, action: str = "withdraw", plan_limit: int = MAX_PLAN_ROWS) -> dict:
    graph = await relationship_graph(session)
    quote = session.bind.dialect.identifier_preparer.quote
    paths = relationship_paths(graph)
    dependencies: dict[str, dict[str, int]] = {}
    relation_hashes = {}
    for index, path in enumerate(paths):
        joins = []
        for level, edge in enumerate(path):
            target = "l" if level == len(path) - 1 else f"c{level + 1}"
            conditions = " AND ".join(
                f"c{level}.{quote(child)} = {target}.{quote(parent)}"
                for child, parent in zip(edge["columns"], edge["parent_columns"])
            )
            joins.append(f"JOIN public.{quote(edge['parent'])} {target} ON {conditions}")
        sql = f"""SELECT l.id::text, count(*),
            encode(sha256(convert_to(string_agg(encode(sha256(convert_to(to_jsonb(c0)::text, 'UTF8')), 'hex'),
                '' ORDER BY to_jsonb(c0)::text), 'UTF8')), 'hex')
            FROM public.{quote(path[0]['table'])} c0 {' '.join(joins)} GROUP BY l.id ORDER BY l.id"""
        records = (await session.execute(text(sql))).all()
        relation_hashes[f"{index}:{path[0]['table']}"] = [list(row) for row in records]
        for listing_id, count, _hash in records:
            counts = dependencies.setdefault(listing_id, {})
            counts[path[0]["table"]] = counts.get(path[0]["table"], 0) + count
    rows = (await session.execute(text("""SELECT id::text, rental_mode, monthly_price, status,
        deleted_at, is_external, primary_source, city, bills_included, bills_text,
        source_price_currency, source_price_period, source_price_is_from, video_asset_id::text,
        encode(sha256(convert_to(to_jsonb(l)::text, 'UTF8')), 'hex') AS row_digest
        FROM listings l ORDER BY id"""))).mappings().all()
    media = (await session.execute(text("""SELECT DISTINCT m.id::text,
        encode(sha256(convert_to(to_jsonb(m)::text, 'UTF8')), 'hex')
        FROM media_assets m WHERE EXISTS (SELECT 1 FROM listing_images i WHERE i.media_asset_id = m.id)
        OR EXISTS (SELECT 1 FROM listings l WHERE l.video_asset_id = m.id) ORDER BY m.id::text"""))).all()
    database = (await session.execute(text("""SELECT current_database(), oid::text FROM pg_database
        WHERE datname = current_database()"""))).one()
    summary: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    cities: Counter[str] = Counter()
    candidates = []
    for row in rows:
        result = listing_eligibility(SimpleNamespace(**row))
        summary["total"] += 1
        if row["deleted_at"] is not None:
            summary["already_deleted"] += 1
            continue
        if result.eligible:
            summary["eligible"] += 1
            if row["monthly_price"] == 1000:
                summary["exactly_1000_base_rent"] += 1
            continue
        summary["ineligible"] += 1
        summary[result.reason or "unclassified_policy_rejection"] += 1
        origin = row["primary_source"] or ("external_unknown" if row["is_external"] else "owner_created")
        statuses[row["status"]] += 1
        sources[origin] += 1
        cities[row["city"]] += 1
        counts = dependencies.get(row["id"], {})
        exclusions = hard_delete_exclusions(counts)
        # Already withdrawn rows remain inventoried but require no repeat write.
        selected_action = action if action == "purge" and not exclusions else "withdraw"
        candidates.append({"id": row["id"], "reason": result.reason, "status": row["status"],
            "is_external": row["is_external"], "source": origin, "city": row["city"],
            "monthly_price": row["monthly_price"], "rental_mode": row["rental_mode"],
            "row_digest": row["row_digest"], "dependencies": counts, "hard_delete_exclusions": exclusions,
            "video_asset_id": row["video_asset_id"], "action": selected_action})
    selected = [row["id"] for row in candidates if row["action"] == "purge" or row["status"] != "closed"][:plan_limit]
    return seal({"format_version": 1, "policy_version": POLICY_VERSION,
        "generated_at": datetime.now(UTC).isoformat(), "database": list(database), "plan_action": action,
        "plan_limit": plan_limit, "selected_ids": selected, "summary": dict(summary),
        "invalid_by_status": dict(statuses), "invalid_by_source": dict(sources), "invalid_by_city": dict(cities),
        "candidates": candidates, "foreign_key_graph": graph,
        "catalog_digest": digest([(row["id"], row["row_digest"]) for row in rows]),
        "relation_digest": digest(relation_hashes), "media_digest": digest([list(row) for row in media]),
        "assumptions": ["Owner monthlyPrice is EUR/month; external rows require explicit source evidence.",
            "Unknown/range/from/recurring costs fail closed. Deposits do not affect monthly rent.",
            "No media assets, object-storage keys, accounts or protected historical relationships are deleted."]})


def verify_recovery(receipts: list[Path], generated_at: str) -> None:
    required = {"postgres", "minio"}
    now = datetime.now(UTC)
    for path in receipts:
        if not path.is_file():
            raise ValueError("Missing verified recovery receipt")
        if os.name != "nt" and path.stat().st_mode & 0o077:
            raise ValueError("Recovery receipts must be private (mode 600)")
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if get_settings().is_production:
            key = os.environ.get("BACKUP_AUTHENTICATION_KEY", "")
            mac_path = Path(str(path) + ".hmac")
            if len(key) < 32 or not mac_path.is_file() or not hmac.compare_digest(
                    mac_path.read_bytes(), hmac.digest(key.encode(), path.read_bytes(), "sha256")):
                raise ValueError("Recovery proof must be authenticated by the production restore tooling")
        kind = receipt.get("kind")
        if kind not in required or receipt.get("restored") is not True:
            raise ValueError("Both successful PostgreSQL and MinIO restore drills are required")
        verified = datetime.fromisoformat(receipt["verified_at"])
        if not datetime.fromisoformat(generated_at) <= verified <= now or now - verified > timedelta(hours=6):
            raise ValueError("Restore proof must follow this manifest and be less than six hours old")
        backup = Path(receipt["backup"])
        if not backup.is_file() or not backup.name.endswith(".enc"):
            raise ValueError("Missing encrypted backup")
        age = now - datetime.fromtimestamp(backup.stat().st_mtime, UTC)
        if not timedelta(0) <= age <= timedelta(hours=72):
            raise ValueError("Encrypted backup must be less than 72 hours old")
        h = hashlib.sha256()
        with backup.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(chunk)
        if h.hexdigest() != receipt.get("sha256"):
            raise ValueError("Verified backup bytes have changed")
        required.remove(kind)
    if required:
        raise ValueError("Incomplete recovery evidence")


async def apply_plan(session, reviewed: dict, *, confirmation: str, recovery_receipts: list[Path]) -> dict:
    verify_manifest(reviewed)
    expected = f"{reviewed['plan_action'].upper()}:{reviewed['digest']}"
    if confirmation != expected:
        raise ValueError("Explicit confirmation must match this exact reviewed plan and action")
    verify_recovery(recovery_receipts, reviewed["generated_at"])
    if get_settings().is_production and os.environ.get("RENTAL_POLICY_RELEASE_LOCK_HELD") != "1":
        raise ValueError("Use the locked production apply wrapper with all writers stopped")
    graph = await relationship_graph(session)
    quote = session.bind.dialect.identifier_preparer.quote
    tables = {"listings", "media_assets", *(edge["table"] for path in relationship_paths(graph) for edge in path)}
    # Locks cover the reviewed catalog and dependencies, preventing a new
    # reference or repricing between verification and the bounded mutation.
    await session.execute(text("LOCK TABLE " + ", ".join(f"public.{quote(name)}" for name in sorted(tables)) + " IN ACCESS EXCLUSIVE MODE"))
    fresh = await inventory(session, action=reviewed["plan_action"], plan_limit=reviewed["plan_limit"])
    if snapshot_digest(fresh) != snapshot_digest(reviewed):
        raise ValueError("Database or dependency snapshot changed; generate and review a new manifest")
    counts: Counter[str] = Counter()
    for row in reviewed["candidates"]:
        if row["id"] not in reviewed["selected_ids"]:
            continue
        listing_id = UUID(row["id"])
        listing = await session.get(Listing, listing_id)
        if listing is None or listing_eligibility(listing).eligible:
            raise ValueError("A candidate no longer matches its approved eligibility state")
        if row["action"] == "purge":
            if row["hard_delete_exclusions"]:
                raise ValueError("Protected relationships cannot be purged")
            await session.execute(delete(Listing).where(Listing.id == listing_id))
            counts["purged"] += 1
        else:
            session.add(ListingStatusHistory(listing_id=listing_id, from_status=listing.status, to_status="closed"))
            listing.status = "closed"
            listing.closed_reason = "rental_policy"
            counts["withdrawn"] += 1
        session.add(AuditLog(action=f"rental_policy.{row['action']}", target_type="listing", target_id=listing_id,
            detail={"manifest_digest": reviewed["digest"], "reason": row["reason"], "policy_version": POLICY_VERSION}))
    if counts:
        await touch_catalog(session)
    await session.flush()
    from ..services.rental_policy import public_eligibility_clause
    invalid_public = await session.scalar(select(Listing.id).where(
        Listing.status == "published", Listing.deleted_at.is_(None), ~func.coalesce(public_eligibility_clause(), False)).limit(1))
    # Other deferred batches can still have published legacy status; public
    # reads exclude them through the authoritative clause from deployment.
    counts["deferred_candidates"] = len(reviewed["candidates"]) - len(reviewed["selected_ids"])
    result = {"manifest_digest": reviewed["digest"], "results": dict(counts),
        "legacy_published_rows_remaining": invalid_public is not None, "media_objects_deleted": 0}
    return result


def reserve_private_output(path: Path) -> int:
    """Reserve a new 0600 file before entering a maintenance transaction.

    O_EXCL and O_NOFOLLOW reject pre-existing destinations and symlinks.
    Never chmod an arbitrary existing parent supplied by the operator.
    """
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    return os.open(path, flags, 0o600)


def save_private_text(path: Path, content: str) -> None:
    fd = reserve_private_output(path)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(content)


def save_report(path: Path, report: dict) -> None:
    save_private_text(path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")


async def execute(args) -> dict:
    # Refuse unwritable/occupied output paths BEFORE any transactional mutation.
    report_fd = reserve_private_output(args.output)
    committed = False
    try:
        async with SessionLocal() as session, session.begin():
            if args.apply:
                if not args.manifest:
                    raise ValueError("Apply requires a previously reviewed manifest")
                reviewed = json.loads(args.manifest.read_text(encoding="utf-8"))
                report = await apply_plan(session, reviewed, confirmation=args.confirm,
                                          recovery_receipts=args.recovery_receipt)
            else:
                await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
                report = await inventory(session, action=args.action, plan_limit=args.plan_limit)
        committed = True
        try:
            with os.fdopen(report_fd, "w", encoding="utf-8") as stream:
                report_fd = -1
                json.dump(report, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
        except Exception as exc:
            # I/O errors and serialization failures both happen AFTER commit.
            # Keep the reserved output and never encourage a blind retry.
            raise RuntimeError(
                "Database transaction may already be COMMITTED, but output writing failed. "
                "Do not repeat cleanup without checking database state and manifest."
            ) from exc
    except BaseException:
        if report_fd >= 0:
            os.close(report_fd)
        if not committed:
            args.output.unlink(missing_ok=True)
        raise
    if not args.apply:
        summary = args.output.with_suffix(".summary.md")
        save_private_text(summary, "# Rental policy inventory\n\n" + json.dumps({
            "digest": report["digest"], "summary": report["summary"],
            "selected": len(report["selected_ids"]), "invalid_by_source": report["invalid_by_source"],
            "invalid_by_status": report["invalid_by_status"], "assumptions": report["assumptions"],
        }, ensure_ascii=False, indent=2) + "\n")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--action", choices=("withdraw", "purge"), default="withdraw")
    parser.add_argument("--plan-limit", type=int, default=MAX_PLAN_ROWS)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--confirm", default="")
    parser.add_argument("--recovery-receipt", type=Path, action="append", default=[])
    args = parser.parse_args(argv)
    if not 1 <= args.plan_limit <= MAX_PLAN_ROWS:
        parser.error("--plan-limit must be between 1 and 500")
    if args.apply and (not args.manifest or not args.confirm or len(args.recovery_receipt) != 2):
        parser.error("Apply requires an exact manifest, confirmation and two recovery receipts")
    report = asyncio.run(execute(args))
    print(json.dumps({"output": str(args.output), "digest": report.get("digest", report.get("manifest_digest")),
        "summary": report.get("summary", report.get("results"))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
