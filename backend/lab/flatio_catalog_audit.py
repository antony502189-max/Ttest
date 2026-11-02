"""Explicit authorized Flatio pilot. No application DB or outbound LLM payload."""
import argparse
import asyncio
import hashlib
import json
import re
import time
import urllib.robotparser
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from xml.etree import ElementTree

import httpx

from app.external_sources import FlatioSource, is_in_import_scope, json_ld
from app.schemas.ai_fact_bridge import BridgeReference
from app.schemas.ai_listing_facts import FactKey
from app.services.ai_flatio_pilot import prepare_flatio_room
from app.services.rental_price_limit import long_term_price_allowed


async def collect(output: Path):
    if output.exists():
        raise ValueError("new private output directory required")
    output.mkdir(parents=True)
    source = object.__new__(FlatioSource)
    robots = urllib.robotparser.RobotFileParser()
    stats = {"started_at": datetime.now(UTC).isoformat(), "raw_persisted": False, "external_llm_calls": 0,
             "maximum_unique_details": 100, "scope": "santa_cruz", "failures": Counter()}
    last = 0.0

    async def guard(request):
        u = request.url
        if (u.scheme != "https" or u.host != "www.flatio.com" or u.username or u.password or u.port not in (None, 443)
                or u.query or not (u.path == "/robots.txt" or str(u) in source.discovery_urls or source.is_listing_url(str(u)))):
            raise ValueError("unapproved destination")
        if u.path != "/robots.txt" and not robots.can_fetch("TtestCatalogAudit", str(u)):
            raise ValueError("robots denied")

    async with httpx.AsyncClient(timeout=25, follow_redirects=False, headers={
        "User-Agent": "TtestCatalogAudit/1.0", "Accept-Language": "en"}, event_hooks={"request": [guard]}) as client:
        async def get(url):
            nonlocal last
            await asyncio.sleep(max(0, 1.0 - (time.monotonic() - last)))
            client.cookies.clear()
            last = time.monotonic()
            async with client.stream("GET", url) as response:
                if response.status_code != 200:
                    raise ValueError("HTTP_" + str(response.status_code))
                parts, size = [], 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > 4_194_304:
                        raise ValueError("response_bound")
                    parts.append(chunk)
                return b"".join(parts).decode("utf-8")
        rules = await get("https://www.flatio.com/robots.txt")
        robots.parse(rules.splitlines())
        stats["robots_sha256"] = hashlib.sha256(rules.encode()).hexdigest()
        urls = set()
        for url in source.discovery_urls:
            document = await get(url)
            for node in ElementTree.fromstring(document).iter():
                if node.tag.endswith("}loc") and node.text:
                    candidate = node.text.strip()
                    if source.is_listing_url(candidate) and source._target_room_sitemap_url(candidate):
                        urls.add(candidate)
        stats["discovered_in_scope_routes"] = len(urls)
        records = []
        fields_coverage = Counter()
        for url in sorted(urls)[:100]:
            try:
                document = await get(url)
                if source._challenge_type(document):
                    raise ValueError("access_challenge")
                rooms = [item for item in json_ld(document) if any(t in str(item.get("@type", "")).lower()
                                                                 for t in ("room", "apartment"))]
                if len(rooms) != 1:
                    raise ValueError("ambiguous_or_missing_jsonld")
                room = rooms[0]
                record_id = re.search(r"/(\d+)(?:-|/|$)", httpx.URL(url).path).group(1)
                listing_id = uuid5(NAMESPACE_URL, "flatio-closed-listing:" + record_id)
                source_id = uuid5(NAMESPACE_URL, "flatio-closed-source:" + record_id)
                ref = BridgeReference(source_record_id=source_id, canonical_listing_id=listing_id,
                                      source_identifier="Flatio:" + record_id, snapshot_hash="a" * 64)
                ready = prepare_flatio_room(room, ref)
                address = room.get("address") or {}
                price = next((f.typed_value.amount for f in ready.facts if f.key == "price"), None)
                reasons = []
                location = {"province": address.get("addressRegion"), "city": address.get("addressLocality"),
                            "country": address.get("addressCountry")}
                if not is_in_import_scope(location, "santa_cruz"):
                    reasons.append("unconfirmed_province")
                small_unit = "/rent/room/" in url or room.get("accommodationCategory") == "Studio" or room.get("numberOfBedrooms") == 1
                if not small_unit:
                    reasons.append("out_of_scope_unit")
                if not long_term_price_allowed("long", price):
                    reasons.append("economic_guard")
                if ready.sanitized_fields["metadata.in_stock"] != "true":
                    reasons.append("not_in_stock")
                record = {"record_id": record_id, "source_id": str(source_id), "listing_id": str(listing_id),
                          "url": url, "checked_at": datetime.now(UTC).isoformat(), "eligible": not reasons,
                          "exclusions": reasons, "location_policy": "existing_santa_cruz_structured_location", "source_hash": hashlib.sha256(json.dumps(room,sort_keys=True).encode()).hexdigest(),
                          "fields": ready.sanitized_fields, "facts": [f.model_dump(mode="json") for f in ready.facts]}
                records.append(record)
                for f in ready.facts:
                    fields_coverage[f.key + ":" + f.status] += 1
                del document, room, rooms, ready
            except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError) as error:
                # Stable failure category only; never retain provider text/headers.
                reason = str(error) if re.fullmatch(r"HTTP_\d+|access_challenge|response_bound|ambiguous_or_missing_jsonld", str(error)) else type(error).__name__
                stats["failures"][reason] += 1
                if reason in {"HTTP_403", "HTTP_429", "access_challenge"}:
                    stats["stopped_on_access_gate"] = True
                    break
        stats.update(finished_at=datetime.now(UTC).isoformat(), attempted=min(100,len(urls)),
                     parsed=len(records), eligible=sum(r["eligible"] for r in records),
                     exclusions=dict(Counter(x for r in records for x in r["exclusions"])),
                     source_field_status=dict(fields_coverage))
        from typing import get_args
        stats["source_field_denominators"] = {key: {"records": len(records), "observed": sum(any(f["key"] == key for f in r["facts"]) for r in records)} for key in get_args(FactKey)}
        (output / "records.json").write_text(json.dumps(records), encoding="utf-8")
        (output / "summary.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
        print(json.dumps(stats), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(collect(parser.parse_args().output))
