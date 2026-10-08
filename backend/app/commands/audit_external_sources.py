"""Bounded public contract audit for external room-listing adapters.

This command performs no database writes and stores no page HTML. It verifies the
public chain discovery -> detail fetch -> parse -> normalize for every adapter.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx

from ..external_sources import (
    AlquilerDocenteCanariasSource,
    DiscoveryResult,
    ExternalListingSource,
    FlatioSource,
    FotocasaSource,
    IdealistaSource,
    MilanunciosSource,
    PisoCompartidoSource,
    PisosSource,
    SourceBlocked,
    ThinkSpainSource,
    clean,
    embedded_json,
    is_in_target_province,
    is_rental,
    is_room_offer,
    parse_price,
)
from ..habitaclia_source import HabitacliaSource
from ..rental_classification import bedroom_count, property_type, rental_price

SOURCE_TYPES = (
    IdealistaSource,
    FotocasaSource,
    MilanunciosSource,
    PisoCompartidoSource,
    PisosSource,
    ThinkSpainSource,
    AlquilerDocenteCanariasSource,
    FlatioSource,
    HabitacliaSource,
)


@dataclass
class DetailAudit:
    url: str
    fetched: bool = False
    parsed: bool = False
    normalized: bool = False
    room_offer: bool | None = None
    rental: bool | None = None
    target_province: bool | None = None
    title: str = ""
    city: str = ""
    source_price_text: str = ""
    map_point: bool | None = None
    latitude: float | None = None
    longitude: float | None = None
    document_bytes: int = 0
    fetch_method: str = ""
    http_status: int | None = None
    final_url: str = ""
    html_title: str = ""
    h1_count: int = 0
    embedded_json_objects: int = 0
    error: str | None = None
    property_type: str | None = None
    source_property_type: str = ""
    rental_mode: str | None = None
    province: str = ""
    bedroom_count: int | None = None
    source_rental_category: str = ""
    parsed_price_amount: int | None = None
    parsed_price_period: str | None = None
    rejection_reason: str | None = None
    photos: int = 0


@dataclass
class SourceAudit:
    source: str
    status: str = "error"
    elapsed_seconds: float = 0.0
    discovered_urls: int = 0
    discovery_complete: bool = False
    visited_pages: int = 0
    expected_total: int | None = None
    discovery_roots: dict[str, dict[str, Any]] = field(default_factory=dict)
    failed_pages: int = 0
    blocked: bool = False
    fetched_details: int = 0
    normalized_details: int = 0
    mapped_details: int = 0
    details: list[DetailAudit] = field(default_factory=list)
    page_diagnostics: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    discovered_by_mode: dict[str, int] = field(default_factory=lambda: {"long": 0, "holiday": 0, "unknown": 0})
    classified_sample_by_mode: dict[str, int] = field(default_factory=lambda: {"long": 0, "holiday": 0})
    accepted_by_mode: dict[str, int] = field(default_factory=lambda: {"long": 0, "holiday": 0})
    accepted_by_property: dict[str, int] = field(default_factory=dict)


def _safe_error(exc: BaseException) -> str:
    text = " ".join(str(exc).split())
    return f"{type(exc).__name__}: {text[:300]}" if text else type(exc).__name__


async def audit_source(
    source: ExternalListingSource,
    *,
    max_pages: int,
    max_details: int,
    source_timeout: float,
    detail_timeout: float,
) -> SourceAudit:
    started = time.perf_counter()
    result = SourceAudit(source=source.name)
    source.max_discovery_pages = max_pages

    async def run() -> None:
        try:
            discovery = await source.discover_listing_urls()
        except SourceBlocked as exc:
            result.status = "blocked"
            result.blocked = True
            result.error = _safe_error(exc)
            return
        except (httpx.HTTPError, RuntimeError, OSError) as exc:
            result.status = "error"
            result.error = _safe_error(exc)
            return

        if isinstance(discovery, DiscoveryResult):
            urls = sorted(discovery.urls)
            result.discovery_complete = discovery.complete
            result.visited_pages = discovery.visited_pages
            result.expected_total = discovery.expected_total
            result.discovery_roots = discovery.roots
            result.failed_pages = len(discovery.failed_pages)
            result.blocked = discovery.blocked
        else:
            urls = sorted(discovery)
            result.discovery_complete = True
            result.visited_pages = 1

        result.discovered_urls = len(urls)
        for url in urls:
            mode = "holiday" if "/holiday-rentals/" in url else "long" if "/property-to-rent-long-term/" in url else "unknown"
            result.discovered_by_mode[mode] += 1
        result.page_diagnostics = [
            {
                "method": diagnostic.get("method"),
                "status": diagnostic.get("status"),
                "final_url": diagnostic.get("final_url"),
                "title": clean(diagnostic.get("title"))[:160],
                "anchor_count": diagnostic.get("anchor_count"),
            }
            for diagnostic in source.discovery_diagnostics.values()
        ]
        for url in urls[:max_details]:
            detail = DetailAudit(url=url)
            result.details.append(detail)
            try:
                document = await asyncio.wait_for(source.fetch_listing(url), timeout=detail_timeout)
                if not document:
                    detail.error = "detail returned no document"
                    continue
                detail.fetched = True
                result.fetched_details += 1
                detail.document_bytes = len(document.encode("utf-8", errors="replace"))
                diagnostic = source.discovery_diagnostics.get(url, {})
                detail.fetch_method = str(diagnostic.get("method") or "")
                detail.http_status = diagnostic.get("status")
                detail.final_url = str(diagnostic.get("final_url") or "")[:500]
                detail.html_title = clean(diagnostic.get("title"))[:160]
                detail.h1_count = document.casefold().count("<h1")
                detail.embedded_json_objects = len(embedded_json(document))
                data = source.parse_listing(document, url)
                detail.parsed = True
                detail.title = clean(data.get("title"))[:160]
                detail.city = clean(data.get("city") or data.get("municipality"))[:100]
                detail.source_price_text = clean(data.get("price_text"))[:80]
                detail.room_offer = is_room_offer(data)
                detail.rental = is_rental(data)
                detail.target_province = is_in_target_province(data)
                detail.property_type = property_type(data, source.name)
                detail.source_property_type = clean(data.get("property_type"))
                detail.province = clean(data.get("province"))
                detail.bedroom_count = bedroom_count(data)
                detail.source_rental_category = clean(data.get("rental_category"))
                detail.photos = len(data.get("images") or [])
                amount, _, period, _ = parse_price(str(data.get("price_text", "")))
                detail.parsed_price_amount, detail.parsed_price_period = amount, period
                price = rental_price(data, source.name, amount, period)
                if price:
                    detail.rental_mode = price.mode
                    result.classified_sample_by_mode[price.mode] += 1
                normalized = source.normalize_listing(data, url)
                if normalized is None:
                    detail.rejection_reason = (
                        "missing_bedroom_evidence" if detail.property_type is None and detail.bedroom_count is None
                        and detail.source_property_type in {"apartment", "flat", "piso", "apartamento"}
                        else "unsupported_property_type" if detail.property_type is None
                        else "missing_or_wrong_location" if not source.accepts_location(data) or not detail.city
                        else "invalid_price" if amount is None or amount <= 0
                        else "ambiguous_price_period" if period is None
                        else "invalid_rental_classification" if price is None
                        else "non_holiday_rental" if source.scope_key.endswith(":holiday") and price.mode != "holiday"
                        else "normalization_failed"
                    )
                if normalized is not None:
                    detail.normalized = True
                    result.normalized_details += 1
                    result.accepted_by_mode[normalized.rental_mode] += 1
                    result.accepted_by_property[normalized.room_type] = result.accepted_by_property.get(normalized.room_type, 0) + 1
                    detail.title = normalized.title[:160]
                    detail.city = normalized.city[:100]
                    detail.source_price_text = normalized.source_price_text[:80]
                    detail.photos = len(normalized.photos)
                    detail.latitude = normalized.latitude
                    detail.longitude = normalized.longitude
                    detail.map_point = normalized.latitude is not None and normalized.longitude is not None
                    if detail.map_point:
                        result.mapped_details += 1
            except SourceBlocked as exc:
                result.blocked = True
                detail.error = _safe_error(exc)
            except (httpx.HTTPError, RuntimeError, ValueError, OSError, TimeoutError) as exc:
                detail.error = _safe_error(exc)

        if result.blocked:
            result.status = "blocked"
        elif result.normalized_details:
            # A valid source may intentionally withhold a precise map point.
            # Keep map coverage as a diagnostic while treating its list cards
            # as healthy public catalog results.
            result.status = "healthy"
        elif not result.discovered_urls:
            result.status = "empty" if result.discovery_complete else "discovery_failed"
        elif not result.fetched_details:
            result.status = "detail_failed"
        else:
            result.status = "classification_failed"

    try:
        await asyncio.wait_for(run(), timeout=source_timeout)
    except TimeoutError as exc:
        result.status = "timeout"
        result.error = _safe_error(exc)
    finally:
        result.elapsed_seconds = round(time.perf_counter() - started, 3)
        await source.close()
    return result


async def audit_all(args: argparse.Namespace) -> dict[str, Any]:
    audits: list[SourceAudit] = []
    for source_type in SOURCE_TYPES:
        audits.append(
            await audit_source(
                source_type(),
                max_pages=args.max_pages,
                max_details=args.max_details,
                source_timeout=args.source_timeout,
                detail_timeout=args.detail_timeout,
            )
        )
    healthy = sum(item.status == "healthy" for item in audits)
    return {
        "healthy_sources": healthy,
        "total_sources": len(audits),
        "minimum_healthy": args.minimum_healthy,
        "passed": healthy >= args.minimum_healthy,
        "sources": [asdict(item) for item in audits],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-pages", type=int, default=2)
    parser.add_argument("--max-details", type=int, default=2)
    parser.add_argument("--source-timeout", type=float, default=120)
    parser.add_argument("--detail-timeout", type=float, default=35)
    parser.add_argument("--minimum-healthy", type=int, default=2)
    args = parser.parse_args(argv)
    if not 1 <= args.max_pages <= 3:
        parser.error("--max-pages must be between 1 and 3")
    if not 1 <= args.max_details <= 3:
        parser.error("--max-details must be between 1 and 3")
    if not 15 <= args.source_timeout <= 180:
        parser.error("--source-timeout must be between 15 and 180 seconds")
    if not 5 <= args.detail_timeout <= 60:
        parser.error("--detail-timeout must be between 5 and 60 seconds")
    if not 1 <= args.minimum_healthy <= len(SOURCE_TYPES):
        parser.error(f"--minimum-healthy must be between 1 and {len(SOURCE_TYPES)}")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = asyncio.run(audit_all(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
