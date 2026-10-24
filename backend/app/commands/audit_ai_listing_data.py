"""Aggregate stored source snapshots without crawling or modifying the catalog.

Offline: python -m app.commands.audit_ai_listing_data --input fixtures.json
Database: set AI_AUDIT_DATABASE_URL to an authorized read-only replica/test DSN,
then use --database. The normal application DATABASE_URL/.env is never loaded.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
from collections import Counter, defaultdict
from collections.abc import AsyncIterator, Iterable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError

from ..services.ai_listing_input import clean_evidence_text
from ..services.listing_evidence import extract_policy_evidence

SOURCES = (
    "Idealista",
    "Fotocasa",
    "Milanuncios",
    "PisoCompartido",
    "Pisos",
    "ThinkSpain",
    "AlquilerDocenteCanarias",
    "Flatio",
    "Habitaclia",
)
POLICIES = ("room_capacity", "couples_allowed", "pets_allowed", "children_allowed", "smoking_allowed")
STORED_FACTS = (*POLICIES, "furnished", "bills_included", "empadronamiento_allowed", "amenities")
SELECTED_FIELDS = ("title", "description", "latitude", "longitude", *STORED_FACTS)


class AuditRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source_name: str = Field(min_length=1, max_length=64)
    canonical_listing_id: str = Field(min_length=1, max_length=120)
    current_status: str = "active"
    normalized_payload: dict[str, Any] = Field(default_factory=dict)


def _pct(n: int, total: int) -> float | None:
    return round(100 * n / total, 2) if total else None


class AuditAccumulator:
    def __init__(self) -> None:
        self.sources: dict[str, dict] = {}
        self.groups: dict[str, list[tuple[str, dict]]] = defaultdict(list)

    def add(self, record: AuditRecord) -> None:
        # Output labels are fixed: arbitrary provider strings could contain PII.
        source = record.source_name if record.source_name in SOURCES else "Other"
        bucket = self.sources.setdefault(
            source,
            {
                "counts": Counter(),
                "lengths": [],
                "canonical_ids": set(),
                "policy_states": {field: Counter() for field in POLICIES},
            },
        )
        counts = bucket["counts"]
        counts["records"] += 1
        bucket["canonical_ids"].add(record.canonical_listing_id)
        payload = record.normalized_payload
        raw_title, raw_description = payload.get("title"), payload.get("description")
        title = clean_evidence_text(raw_title if isinstance(raw_title, str) else "")
        description = clean_evidence_text(raw_description if isinstance(raw_description, str) else "")
        length = len(description)
        bucket["lengths"].append(length)
        counts["description_present"] += bool(description)
        counts["title_present"] += bool(title)
        facts = extract_policy_evidence(title=title, description=description)
        for field in POLICIES:
            fact = facts[field]
            bucket["policy_states"][field][fact.status] += 1
            stored = payload.get(field)
            if (
                stored is not None
                and fact.status == "explicit"
                and (type(stored), stored) != (type(fact.value), fact.value)
            ):
                counts["snapshot_evidence_disagreements"] += 1
        amenities = payload.get("amenities")
        counts["amenities_present"] += isinstance(amenities, list) and bool(amenities)
        lat, lng = payload.get("latitude"), payload.get("longitude")
        counts["public_point_present"] += (
            isinstance(lat, (int, float))
            and not isinstance(lat, bool)
            and isinstance(lng, (int, float))
            and not isinstance(lng, bool)
            and math.isfinite(lat)
            and math.isfinite(lng)
            and -90 <= lat <= 90
            and -180 <= lng <= 180
        )
        for field in STORED_FACTS:
            stored = payload.get(field)
            if stored is None or stored == []:
                continue
            counts["stored_fact_values"] += 1
            stored_evidence = facts.get(field)
            if (
                not stored_evidence
                or stored_evidence.status != "explicit"
                or (type(stored), stored) != (type(stored_evidence.value), stored_evidence.value)
            ):
                counts["unknown_provenance_values"] += 1
        # Only active snapshots participate in cross-source conflicts. Unknown
        # values do not vote, and canonical_id groups are never exported.
        if record.current_status == "active":
            signatures: dict[str, tuple[str, bool | int | None]] = {}
            for field in POLICIES:
                value = payload.get(field)
                if (field == "room_capacity" and type(value) is int and 1 <= value <= 99) or (
                    field != "room_capacity" and type(value) is bool
                ):
                    signatures[field] = (type(value).__name__, value)
                fact = facts[field]
                if fact.status == "explicit":
                    # Include contradictions against a stored scalar too.
                    signatures[field + ":text"] = (type(fact.value).__name__, fact.value)
            self.groups[record.canonical_listing_id].append((source, signatures))

    def report(self) -> dict:
        conflicts: Counter[str] = Counter()
        conflicting_canonicals = 0
        for rows in self.groups.values():
            if len(rows) < 2:
                continue
            fields = {
                field
                for field in POLICIES
                if len(
                    {
                        value
                        for _, signatures in rows
                        for key, value in signatures.items()
                        if key.removesuffix(":text") == field
                    }
                )
                > 1
            }
            if fields:
                conflicting_canonicals += 1
                for source, signatures in rows:
                    if any(key.removesuffix(":text") in fields for key in signatures):
                        conflicts[source] += 1
        output = {}
        for source in sorted(set(SOURCES) | set(self.sources)):
            bucket = self.sources.get(source)
            counts = bucket["counts"] if bucket else Counter()
            lengths = sorted(bucket["lengths"]) if bucket else []
            n = counts["records"]
            output[source] = {
                "records": n,
                "canonical_listings": len(bucket["canonical_ids"]) if bucket else 0,
                "title_present_pct": _pct(counts["title_present"], n),
                "description_present_pct": _pct(counts["description_present"], n),
                "description_length": {
                    "min": min(lengths) if lengths else None,
                    "max": max(lengths) if lengths else None,
                    "p50": lengths[math.ceil(0.5 * n) - 1] if n else None,
                    "p95": lengths[math.ceil(0.95 * n) - 1] if n else None,
                    "histogram": {
                        "empty": lengths.count(0),
                        "1_79": sum(1 <= x < 80 for x in lengths),
                        "80_499": sum(80 <= x < 500 for x in lengths),
                        "500_1999": sum(500 <= x < 2000 for x in lengths),
                        "2000_plus": sum(x >= 2000 for x in lengths),
                    },
                },
                "policies": {
                    field: {
                        "explicit_pct": _pct(bucket["policy_states"][field]["explicit"] if bucket else 0, n),
                        "states": {
                            state: bucket["policy_states"][field][state] if bucket else 0
                            for state in ("explicit", "conditional", "conflict", "unknown")
                        },
                    }
                    for field in POLICIES
                },
                "amenities_present_pct": _pct(counts["amenities_present"], n),
                "public_point_present_pct": _pct(counts["public_point_present"], n),
                "geo_confirmed_pct": None,
                "potential_conflicting_source_records": conflicts[source],
                "snapshot_evidence_disagreements": counts["snapshot_evidence_disagreements"],
                "stored_fact_values": counts["stored_fact_values"],
                "unknown_provenance_values": counts["unknown_provenance_values"],
                "unknown_provenance_pct": _pct(counts["unknown_provenance_values"], counts["stored_fact_values"]),
            }
        return {
            "report_version": 1,
            "records": sum(row["records"] for row in output.values()),
            "potential_conflicting_canonical_listings": conflicting_canonicals,
            "methodology": {
                "unit": "source record; canonical counts are distinct within each source",
                "explicit": "bounded evidence reconstructed from stored title/description, not historical provenance",
                "unknown_provenance": "nonnull stored fact without matching explicit text evidence / all nonnull stored facts",
                "conflicts": "active snapshots sharing canonical ID with differing nonnull policy values; potential, not resolved",
                "geo": "coordinate presence does not prove dwelling precision; geo_confirmed_pct unavailable without provenance",
                "amenities": "presence only; no assertion that every amenity is evidence-backed",
                "quantiles": "nearest rank, includes empty descriptions; lengths after contact/markup removal",
                "limitations": "synthetic fixtures are not production coverage; unsupported phrases remain unknown",
            },
            "sources": output,
        }


def audit_records(records: Iterable[AuditRecord]) -> dict:
    accumulator = AuditAccumulator()
    for record in records:
        accumulator.add(record)
    return accumulator.report()


async def database_records(url: str, *, include_inactive: bool) -> AsyncIterator[AuditRecord]:
    # No app configuration/session import: a command cannot accidentally fall
    # back to production settings. PostgreSQL itself enforces read-only mode.
    from sqlalchemy import column, func, select, table
    from sqlalchemy.dialects.postgresql import JSONB
    from sqlalchemy.ext.asyncio import create_async_engine

    if not url.startswith("postgresql+asyncpg://"):
        raise ValueError("Only explicit PostgreSQL asyncpg read-only connections are supported")
    engine = create_async_engine(
        url,
        connect_args={
            "server_settings": {
                "default_transaction_read_only": "on",
                "statement_timeout": "60000",
                "lock_timeout": "3000",
            }
        },
    )
    source = table(
        "external_listing_sources",
        column("source_name"),
        column("canonical_listing_id"),
        column("current_status"),
        column("normalized_payload", JSONB),
    )
    selected = func.jsonb_build_object(
        *[part for field in SELECTED_FIELDS for part in (field, source.c.normalized_payload[field])]
    )
    query = select(source.c.source_name, source.c.canonical_listing_id, source.c.current_status, selected)
    if not include_inactive:
        query = query.where(source.c.current_status == "active")
    try:
        async with engine.connect() as connection:
            connection = await connection.execution_options(isolation_level="REPEATABLE READ")
            transaction = await connection.begin()
            try:
                await connection.exec_driver_sql("SET TRANSACTION READ ONLY")
                async with connection.stream(query.execution_options(yield_per=500)) as result:
                    async for name, listing_id, status, payload in result:
                        yield AuditRecord(
                            source_name=name,
                            canonical_listing_id=str(listing_id),
                            current_status=status,
                            normalized_payload=payload,
                        )
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


def render_markdown(report: dict) -> str:
    lines = [
        "# Stored listing data audit",
        "",
        f"Source records: {report['records']}",
        "",
        "Percentages use source records; N/A means unavailable or no denominator.",
        "",
        "| Source | n | Description % | Capacity explicit % | Couples explicit % | Pets explicit % | Children explicit % | Smoking explicit % | Amenities % | Public point % | Confirmed geo % | Potential conflicts | Unknown provenance % |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    def display(value):
        return "N/A" if value is None else str(value)

    for name, row in report["sources"].items():
        values = [
            name,
            row["records"],
            row["description_present_pct"],
            *(row["policies"][field]["explicit_pct"] for field in POLICIES),
            row["amenities_present_pct"],
            row["public_point_present_pct"],
            row["geo_confirmed_pct"],
            row["potential_conflicting_source_records"],
            row["unknown_provenance_pct"],
        ]
        lines.append("| " + " | ".join(map(display, values)) + " |")
    lines.extend(
        [
            "",
            "Full distributions, states and methodology:",
            "",
            "```json",
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


async def _database_report(url: str, include_inactive: bool) -> dict:
    accumulator = AuditAccumulator()
    async for record in database_records(url, include_inactive=include_inactive):
        accumulator.add(record)
    return accumulator.report()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--input", type=Path, help="Offline JSON array of source snapshots")
    mode.add_argument(
        "--database", action="store_true", help="Use dedicated AI_AUDIT_DATABASE_URL environment variable"
    )
    parser.add_argument("--include-inactive", action="store_true")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.input:
            records = [
                AuditRecord.model_validate(value) for value in json.loads(args.input.read_text(encoding="utf-8"))
            ]
            report = audit_records(
                record for record in records if args.include_inactive or record.current_status == "active"
            )
        else:
            url = os.environ.get("AI_AUDIT_DATABASE_URL")
            if not url:
                parser.error("AI_AUDIT_DATABASE_URL must explicitly select an authorized read-only/test database")
            report = asyncio.run(_database_report(url, args.include_inactive))
        report["selection"] = {
            "mode": "offline" if args.input else "database",
            "statuses": "all" if args.include_inactive else "active",
        }
        rendered = (
            render_markdown(report)
            if args.format == "markdown"
            else json.dumps(
                report,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
        if args.output:
            if args.input and args.output.resolve() == args.input.resolve():
                raise ValueError("Output must not overwrite input")
            args.output.write_text(rendered, encoding="utf-8")
        else:
            print(rendered, end="")
        return 0
    except (OSError, ValueError, TypeError, SQLAlchemyError, TimeoutError):
        # Driver/validation exceptions can contain DSNs or the original payload.
        print("Audit failed: check input schema, dedicated read-only connection and output path.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
