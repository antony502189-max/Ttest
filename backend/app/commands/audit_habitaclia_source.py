"""Bounded live audit for the staged Habitaclia room source.

The command is read-only: it crawls the public Tenerife rental catalogue,
filters room-like detail URLs, fetches a bounded number of details, and verifies
that at least one current listing survives the conservative room normalizer.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from typing import Any
from urllib.parse import urljoin

import httpx

from ..habitaclia_source import HabitacliaSource


def _diagnostics(source: HabitacliaSource) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for url, diagnostic in list(source.discovery_diagnostics.items())[:12]:
        hrefs = [str(href) for href in diagnostic.get("hrefs", [])]
        diagnostics.append(
            {
                "url": url,
                "method": diagnostic.get("method"),
                "status": diagnostic.get("status"),
                "final_url": diagnostic.get("final_url"),
                "title": diagnostic.get("title"),
                "anchor_count": diagnostic.get("anchor_count"),
                "href_samples": hrefs[:12],
                "alquiler_href_samples": [href for href in hrefs if "alquiler" in href.casefold()][:12],
            }
        )
    return diagnostics


def _plain_context(document: str, start: int, end: int) -> str:
    fragment = document[max(0, start - 420) : min(len(document), end + 420)]
    fragment = re.sub(r"<script\b.*?</script>", " ", fragment, flags=re.IGNORECASE | re.DOTALL)
    fragment = re.sub(r"<style\b.*?</style>", " ", fragment, flags=re.IGNORECASE | re.DOTALL)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", fragment).strip()[:700]


def _catalog_probe(source: HabitacliaSource, document: str, base_url: str) -> dict[str, Any]:
    """Expose bounded route/card evidence when the catalogue contract changes."""
    attribute_values = re.findall(
        r'(?:href|data-url|data-href|data-link|content)\s*=\s*["\']([^"\']+)["\']',
        document,
        re.IGNORECASE,
    )
    route_pattern = re.compile(
        r"(?:https?://(?:www\.)?habitaclia\.com)?/(?:[^\"'<>\s]*-i\d{8,}\.htm|i\d{8,})(?:[?#][^\"'<>\s]*)?",
        re.IGNORECASE,
    )
    route_values = list(dict.fromkeys(route_pattern.findall(document)))
    attribute_routes = [
        value
        for value in attribute_values
        if re.search(r"(?:-i\d{8,}\.htm|(?:^|/)i\d{8,}(?:$|[?#]))", value, re.IGNORECASE)
    ]
    routes = list(dict.fromkeys([*route_values, *attribute_routes]))
    absolute_routes = [urljoin(base_url, value.replace("&amp;", "&")) for value in routes]
    recognized = [url for url in absolute_routes if source.is_listing_url(url)]

    room_contexts: list[str] = []
    for match in re.finditer(r"habitaci(?:ó|o)n(?:es)?", document, re.IGNORECASE):
        context = _plain_context(document, match.start(), match.end())
        if context and context not in room_contexts:
            room_contexts.append(context)
        if len(room_contexts) >= 8:
            break

    id_tokens = list(dict.fromkeys(re.findall(r"\bi\d{8,}\b", document, re.IGNORECASE)))
    return {
        "document_length": len(document),
        "attribute_count": len(attribute_values),
        "route_samples": absolute_routes[:20],
        "recognized_route_samples": recognized[:20],
        "id_token_samples": id_tokens[:20],
        "room_context_samples": room_contexts,
    }


async def audit(*, max_pages: int, max_details: int, detail_timeout: int) -> tuple[dict[str, Any], int]:
    source = HabitacliaSource()
    source.max_discovery_pages = max_pages
    report: dict[str, Any] = {
        "source": source.name,
        "discovery_url": source.discovery_urls[0],
        "discovery_complete": False,
        "blocked": False,
        "visited_pages": 0,
        "failed_pages": [],
        "candidate_urls": 0,
        "details_checked": 0,
        "accepted_rooms": 0,
        "accepted": [],
        "rejected": [],
        "errors": [],
        "catalog_probe": {},
        "discovery_diagnostics": [],
    }
    try:
        probe_url = source.discovery_urls[0]
        probe_document = await source.request(probe_url)
        if probe_document:
            report["catalog_probe"] = _catalog_probe(source, probe_document, probe_url)
            visible_count = source.visible_result_count(probe_document)
            recognized = report["catalog_probe"].get("recognized_route_samples", [])
            if visible_count and not recognized:
                report["errors"].append(
                    "Visible Habitaclia results exist but the current detail-route contract recognizes no card route"
                )
                report["discovery_diagnostics"] = _diagnostics(source)
                return report, 6

        discovery = await source.discover_listing_urls()
        candidates = sorted(discovery.urls)
        report.update(
            {
                "discovery_complete": discovery.complete,
                "blocked": discovery.blocked,
                "visited_pages": discovery.visited_pages,
                "failed_pages": discovery.failed_pages,
                "candidate_urls": len(candidates),
                "discovery_diagnostics": _diagnostics(source),
            }
        )

        if discovery.blocked:
            report["errors"].append("Habitaclia blocked anonymous public discovery")
            return report, 2
        if not discovery.complete:
            report["errors"].append("Habitaclia discovery did not reach a complete catalogue boundary")
            return report, 3
        if not candidates:
            report["errors"].append("No room-like Habitaclia detail URLs were discovered")
            return report, 4

        for url in candidates[:max_details]:
            report["details_checked"] += 1
            try:
                document = await asyncio.wait_for(source.fetch_listing(url), timeout=detail_timeout)
                if not document:
                    report["errors"].append(f"No detail document: {url}")
                    continue
                data = source.parse_listing(document, url)
                item = source.normalize_listing(data, url)
                if item is None:
                    report["rejected"].append(url)
                    continue
                report["accepted_rooms"] += 1
                report["accepted"].append(
                    {
                        "external_id": item.external_id,
                        "url": item.source_url,
                        "title": item.title,
                        "city": item.city,
                        "price_amount": item.price_amount,
                        "price_period": item.price_period,
                    }
                )
            except (TimeoutError, httpx.HTTPError, RuntimeError, TypeError, ValueError) as exc:
                report["errors"].append(f"{url}: {type(exc).__name__}: {exc}")

        report["discovery_diagnostics"] = _diagnostics(source)
        if not report["accepted_rooms"]:
            report["errors"].append("No checked Habitaclia candidate normalized as a current room rental")
            return report, 5
        return report, 0
    finally:
        await source.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=30)
    parser.add_argument("--max-details", type=int, default=20)
    parser.add_argument("--detail-timeout", type=int, default=35)
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    if args.max_pages < 1 or args.max_details < 1 or args.detail_timeout < 1:
        raise SystemExit("audit bounds must be positive")

    report, return_code = asyncio.run(
        audit(max_pages=args.max_pages, max_details=args.max_details, detail_timeout=args.detail_timeout)
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        from pathlib import Path

        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered + "\n", encoding="utf-8")
    raise SystemExit(return_code)


if __name__ == "__main__":
    main()
