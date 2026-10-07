# Pre-implementation parser inventory (2026-10-07)

Baseline: `22eb2be4a6501f9f84bed3cb429aced289905ffb`, fresh origin/main.
The original working directory has unrelated modified screenshots and a corrupt
Codex checkpoint ref; implementation uses a separate clean checkout.

## Existing chain and contracts

`configured_sources()` returns adapters from `app.external_sources`.
Production also installs `HabitacliaSource` using `install_habitaclia_source()`.
`ExternalListingSource.discover_listing_urls()` returns `DiscoveryResult`;
`run_source()` fetches details in batches of 100, under the configured semaphore,
parses, checks room/rental/geography, normalizes, and calls `upsert()`.
`NormalizedListing` becomes `Listing` plus `ExternalListingSource` source rows.
Snapshots, raw payload, fingerprint, scope, seen/check timestamps and lifecycle
are already persisted. `Listing.rental_mode` is **long / holiday**. `room_type`
is a string, and `Listing.bedroom_count` already exists. Monthly, nightly and
weekly prices are separate nullable columns. No migration is necessary.

`upsert()` first looks up source/external ID, then source/source URL. Photo
matching uses `duplicate_listing_id(... rental_mode=...)` and a PostgreSQL
advisory guard; same-source repost matching additionally requires metadata and
strong gallery overlap. Image import already reconciles a bounded gallery,
uses unique media keys, and does not mirror external videos.

`archive_missing()` only runs after complete discovery and successful details;
state probes preserve unknown/error states. `deactivate_source_record()` and
`promote_best_active_source()` preserve canonical offers with active backups.
`run_once()` owns a local and Redis lease, heartbeat, healthy-source gate, then
at most eight due enabled province scopes when the nationwide flag is true.
Scope uniqueness is `(source_name, scope_key)`; disabled defaults already exist.
`completed_source_contract()` requires discovered, fetched, accepted and a
publishable outcome; partial sources do not count as healthy.

## Sources before changes

| Source / class | Default | Discovery | Classification / structure | Pagination / location |
|---|---|---|---|---|
| Pisos / PisosSource | yes | two Tenerife room routes | artificially appended room category; generic JSON-LD / embedded taxonomy | generic links; municipality slug fallback only Santa Cruz |
| PisoCompartido / PisoCompartidoSource | yes | Santa Cruz rooms | room category; server HTML + generic JSON-LD | pagination only accepts `habitaciones_`, while published route uses `habitaciones-` |
| Flatio / FlatioSource | yes | two global offer sitemaps, Santa Cruz room slug filter | Room JSON-LD; EUR/MON, InStock required | ignores page budget; room-only URLs, country omitted |
| AlquilerDocenteCanarias / AlquilerDocenteCanariasSource | yes | WordPress sitemap, Santa Cruz room slugs | HTML title/price/city/property ID | one sitemap; local geography only |
| Fotocasa / FotocasaSource | yes | Santa Cruz sharing | embedded public state + JSON-LD; forced room category | shared-home pagination; no whole-home routes |
| Milanuncios / MilanunciosSource | yes | four Canarias catalogues | own room/studio/one-bedroom classifier, accepts bare loft; own normalizer | 120 pages; five-island restriction |
| Idealista / IdealistaSource | no | Santa Cruz rooms | appended room category | generic links / address / geo |
| ThinkSpain / ThinkSpainSource | no | Tenerife long-term | explicit room-only override | generic links / generic JSON-LD |
| Habitaclia / HabitacliaSource | production installation | Tenerife catalogue | own units classifier; fabricated room proxy to shared normalizer | hydrated navigationUrl pagination; deliberately suppresses undocumented map points |

Global `NEGATIVE` rejects estudio and whole-home phrases. The shared normalizer
requires `is_room_offer`; importer repeats it, excluding whole units even when
an adapter supports them. All generic normalized coordinates are additionally
checked against Santa Cruz boxes even for nationwide province scopes. Rental
mode assumes ordinary alquiler means long and weekly price means holiday;
weekly amount also reaches nightly_price unchanged. Fingerprint omits mode.

## Bounded public baseline evidence

One detail per adapter, one generic discovery page, 30s source / 12s detail
budget, no database writes, no browser challenge interactions:

| Source | Discovered | Accepted sample | Observed result |
|---|---:|---:|---|
| Idealista | 0 | 0 | blocked, HTTP 403 |
| Fotocasa | 30 | 1 | accessible sample; discovery budget is partial |
| Milanuncios | 0 | 0 | blocked, HTTP 405 Pardon Our Interruption |
| PisoCompartido | 16 | 0 | fetched sample fails normalization |
| Pisos | 30 | 1 | accessible sample; discovery budget is partial |
| ThinkSpain | 0 | 0 | HTTP 202 empty anonymous response, discovery failed |
| AlquilerDocenteCanarias | 17 | 1 | accessible sitemap/detail sample |
| Flatio | 15 | 0 | fetched sample fails structured availability/price contract |

These are sample counts, **not inventory estimates**, and do not prove all
details work. `pisocompartido.com/zonas/` publicly links mainland, Baleares,
both Canary provinces, Ceuta and Melilla; published routes must be discovered
and validated rather than synthesized. Flatio's first sitemap exposes both
`/rent/room/` and `/rent/apartment/`, including non-Spain offers. ThinkSpain
public holiday catalogue exists but this machine receives empty HTTP 202;
it must not be silently enabled or called healthy. Full local container checks
currently require starting the stopped Docker Linux daemon.

## Implementation boundary

Reuse adapter, importer, scope rows, lease, media and lifecycle. Add explicit
source-aware classification and price cadence, structured province aliases,
bounded published-route discovery/provisioning and an operator bootstrap
calling run_source. Keep production defaults and thresholds. No frontend,
infrastructure, historical reclassification or production bootstrap.

## Verified implementation findings

The PostgreSQL integration run additionally proved canonical bedroom_count's
existing 1..99-or-NULL constraint. Studio count zero is kept in source snapshots
and canonical Estudio taxonomy with NULL count; no schema migration is needed.
An isolated test database passed all nine new Spain import/bootstrap tests. The complete
backend unit audit passed 497 tests (three skipped); later focused parser tests
passed 158 tests after final safety fixes. Production Compose does not forward
the existing nationwide flag; future explicit activation is documented using
one-off container flags / an operator override, without changing defaults.

See [operator runbook](external-spain-parser-operations.md) for the actual final
nine-provider sample, 88 live validated scopes covering all 52 territories,
province sample and the independently verified Pisos 40 EUR/night studio.
No sample proves the desired 2,500 canonicals or 500–1,000 holiday offers.
