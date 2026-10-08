"""Discover published province routes, validate live, provision disabled scopes."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

import httpx

from ..db.session import SessionLocal
from ..external_sources import SourceBlocked
from ..services.external_scopes import (
    PUBLISHED_GEOGRAPHY,
    SOURCE_TYPES,
    ScopeDefinition,
    discover_published_holiday_scopes,
    provision_scopes,
    published_scope_definitions,
    validate_discovery_route,
    validate_scope,
)
from ..spain_provinces import PROVINCES


def read_manifest(path: Path) -> list[ScopeDefinition]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or len(payload) > 468:
        raise ValueError("Manifest must contain at most 468 source/province scopes")
    definitions = [
        validate_scope(ScopeDefinition(value["source_name"], value["scope_key"], tuple(value["discovery_urls"])))
        for value in payload
    ]
    if len({(value.source_name, value.scope_key) for value in definitions}) != len(definitions):
        raise ValueError("Duplicate source/province scopes in manifest")
    return definitions


async def execute(args: argparse.Namespace) -> dict:
    definitions: list[ScopeDefinition] = []
    failures: list[dict] = []
    if args.manifest:
        definitions = read_manifest(args.manifest)
    else:
        for name in args.sources.split(","):
            if getattr(args, "rental_mode", "all") == "holiday":
                source = SOURCE_TYPES[name]()
                try:
                    definitions.extend(await discover_published_holiday_scopes(source))
                except (SourceBlocked, RuntimeError, ValueError, httpx.HTTPError, OSError) as exc:
                    failures.append({"source": name, "error": str(exc)})
                finally:
                    await source.close()
                continue
            if name not in PUBLISHED_GEOGRAPHY:
                raise ValueError("Automatic route discovery supports Pisos and PisoCompartido")
            source = SOURCE_TYPES[name]()
            try:
                document = await source.request(PUBLISHED_GEOGRAPHY[name])
                definitions.extend(published_scope_definitions(name, document or "", PUBLISHED_GEOGRAPHY[name]))
            except (SourceBlocked, RuntimeError, ValueError, httpx.HTTPError, OSError) as exc:
                failures.append({"source": name, "error": str(exc)})
            finally:
                await source.close()
    validated: list[ScopeDefinition] = []
    evidence: list[dict] = []
    for definition in definitions:
        source = SOURCE_TYPES[definition.source_name]()
        source.scope_key = definition.scope_key
        source.discovery_urls = definition.discovery_urls
        try:
            canonical_urls: list[str] = []
            for url in definition.discovery_urls:
                context = {"source": source.name, "scope": source.scope_key, "url": url}
                try:
                    route = await validate_discovery_route(source, url)
                except (SourceBlocked, RuntimeError, ValueError, httpx.HTTPError, OSError) as exc:
                    failure = {**context, "validated": False, "error": f"{type(exc).__name__}: {exc}"[:300]}
                    failures.append(failure)
                    evidence.append(failure)
                    continue
                evidence.append({**context, **route, "validated": True})
                canonical_urls.append(route["final_url"])
            if canonical_urls:
                validated.append(validate_scope(ScopeDefinition(source.name, source.scope_key, tuple(canonical_urls))))
        finally:
            await source.close()
    # Save only validated routes. The default never connects to the DB.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps([asdict(value) for value in validated], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    count = 0
    if args.apply:
        async with SessionLocal() as session:
            count = await provision_scopes(session, validated, enable=args.enable)
    covered = {value.scope_key.removeprefix("province:").removesuffix(":holiday") for value in validated}
    return {
        "dry_run": not args.apply,
        "validated_scopes": len(validated),
        "provisioned": count,
        "enabled_explicitly": bool(args.enable),
        "missing_provinces": sorted(set(PROVINCES) - covered),
        "evidence": evidence,
        "failures": failures,
        "manifest": str(args.output),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", default="Pisos,PisoCompartido")
    parser.add_argument("--rental-mode", choices=("all", "holiday"), default="all")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--enable", action="store_true")
    args = parser.parse_args(argv)
    if args.enable and not args.apply:
        parser.error("--enable requires --apply")
    report = asyncio.run(execute(args))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
