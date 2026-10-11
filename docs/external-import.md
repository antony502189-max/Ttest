# External listing ingestion — operator and developer overview

This page is an entry point to the existing detailed importer runbooks, **not authorization** to enable a new provider, countrywide crawl or data cleanup.

## Architecture

```text
Public provider page/structured detail
   → ExternalListingSource adapter (backend/app/external_sources.py)
   → discovery + normalization + rental classification / price checks
   → run_source / idempotent source identity (backend/app/services/external_import.py)
   → canonical listing, public point (only if explicitly provided), gallery/media
   → PostgreSQL source records + import runs/checkpoints
   → public card search, map markers, detail
```

The background worker is `backend/app/workers/external_listings.py`, configured through the VPS env and supervised as `external-listings-worker`. A healthy process alone is insufficient: the worker checks how many configured sources produced useful accepted listings. Redis coordinates distributed leases; PostgreSQL persists source identities and progress across failures.

Source implementations include adapters for public property listing providers. The definitive source set and availability are determined by `configured_sources()` and the **effective runtime** `EXTERNAL_IMPORT_SOURCES`, not by this document or outdated screenshots.

## Product and data invariants

- Long-term `long` rentals must have a verified monthly price from 1–1,000 EUR inclusive; do not let a legacy parser misread `1 200€` as 200. `holiday` remains an independent mode with valid nightly price.
- Rooms, studios and suitable one-bedroom properties are the relevant catalog categories under present policy. Reject non-residential, sale-only, wanted, bed-only and unsupported offers rather than inventing missing data.
- Canonical deduplication must preserve identity and existing healthy galleries. Broken/partial image fetches are **not** permission to erase previously associated media. Gallery reconciliation has dedicated integrity checks.
- Imported public coordinates may be approximate or absent. Do not fabricate an exact user address from broad provider metadata. Missing coordinates affect community spatial filtering.
- Failed or blocked sources are not evidence that their existing published listings disappeared. Do not close or delete large catalog segments solely because a site blocked anonymous access.
- Respect terms, robots, host restrictions and lawful anonymous access. No CAPTCHA solver, authenticated bypass or scraping circumvention.
- Normal deploy explicitly records `data_maintenance=skipped`; physical removals, catalog cleanups and media deletion need their own approved maintenance protocol.

## Nationwide scopes

Migration 0051 introduced optional per-province source scopes. Scope rows are **disabled by default**; `EXTERNAL_IMPORT_NATIONWIDE_ENABLED` is a separate gate. The gate's actual value in the running VPS may differ from source defaults. Enabling every province at once is not a consequence of adding 17-region browsing: UI scope and importer crawl scope are independent.

Approve a source-specific provider URL and structured province evidence before activating a small scope. Limit per-source concurrency, page and detail budgets; monitor idempotency, accepted count, stable source mapping, latency and disk footprint. Holiday inventory uses independent `province:<name>:holiday` slices, not the residential provider URL.

## Operations: observe before changing

- Read-only operator monitoring: `bash /srv/112233.es/current/deploy/production-monitor-check.sh`.
- Admin inspection (authorized): `GET /api/v1/admin/external-import/worker`, `GET /api/v1/admin/external-import/runs`.
- Inspect logs through active-release Compose: `docker compose --env-file /srv/112233.es/shared/production.env -f /srv/112233.es/current/docker-compose.production.yml logs --tail=200 external-listings-worker`.
- All production scope admissions, removals, cleanup, media management and backup operations require a separate reviewed change plan; test restoration before any destructive action.
- CI/fixture parsers do not prove that current production sources are reachable or useful.

## Detailed documentation

- [Spain parser operator runbook](external-spain-parser-operations.md): admission criteria, province slices, dry runs, pilot steps, recovery.
- [External import catalog contract](external-import-catalog-contract.md): canonical idempotency and useful-source health.
- [Holiday catalog discovery](holiday-rental-operations.md): provider holiday scopes.
- [External removal sweep](external-removal-sweep.md): narrow lifecycle safety.
- [External source implementation inventory](external-rental-implementation-inventory.md): historical/code inventory.
- [Capacity and Spain-scale architecture](spain-scale-architecture.md).
- [Production operations](production-operations.md): locks, backups, rollback and observability.

If a source guide claims its code was "not activated" on the date of that guide, treat it as **dated evidence** and verify current worker flags before taking any operational action.
