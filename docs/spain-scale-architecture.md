# Spain scale catalog architecture

## Inventory and migration boundary

Before this change the production `AppContext` called `getStablePublicCatalog → getPublicListings → fetchAllSearch`, paged through the public catalog, held every listing in memory, and refreshed it when the catalog version changed. Desktop search, mobile results, maps, favorites and similar listings consumed that snapshot. Owner pages already used `/listings/mine`; detail deep links already used `/listings/{id}`. The old `/listings/search` offset endpoint remains for compatibility, but the production UI no longer calls the catalog-all flow.

The production path is now:

```text
PostgreSQL/PostGIS → bounded card search → desktop/mobile results
                   → viewport map query → marker or cluster layer
                   → one detail query → detail page
                   → bounded ID resolution → favorites
                   → owner-specific query → My Listings
```

Mock mode retains its fixture catalog. Production `allListings` is only a small snapshot cache for existing create/edit flows and is never hydrated from all public results or stored as a catalog in localStorage. Saved searches retain filter state and reopen the bounded search route. Discards remain IDs and filter returned pages locally. The home hero and admin data use their separate endpoints. Google Maps remains lazy loaded.

## API contracts and bounds

`POST /api/v1/listings/search/cards` accepts the existing public filters, desktop and mobile sort orders, `limit` 1–50, and an opaque cursor. It returns `{items,total,nextCursor,previousCursor}`. Each item is a card DTO with one cover, a short description and no owner contact or gallery. The cursor fingerprints the filter set and contains the promotion tier, promotion timestamp, requested sort value and UUID tie breaker. It rejects use with a different query. The active TOP tier always precedes ordinary results. The query fetches `limit + 1`; it never traverses pages with a large offset. Exact `total` is a separate count query and may become the dominant cost on very broad nationwide searches; monitor it before enabling nationwide ingestion.

`POST /api/v1/listings/map` requires validated north/south/east/west and zoom, plus the same listing filters. The viewport is applied to the geography column so its GiST index can participate. At zoom 13 or above the server returns at most 300 individual markers. If the viewport has more matches, or at lower zoom, it aggregates into a 20×20 grid, returning at most 400 explicit `cluster` records. Marker records contain ID, position, price, promotion and external source routing only. The browser requests on map idle with debounce, aborts stale requests and retains the camera in URL state. Grid aggregation bounds transfer size, though the database still scans matches in a very dense viewport; query duration metrics and `EXPLAIN (ANALYZE, BUFFERS)` on production-like data are rollout gates.

`POST /api/v1/listings/cards/resolve` takes at most 100 IDs per call; the client batches larger favorite sets. `GET /api/v1/listings/similar/{id}` returns at most three cards. Listing detail stays independent at `GET /api/v1/listings/{id}`. Native owner list APIs remain separate.

## PostgreSQL and geography

Migration 0050 adds a partial `(rental_mode, created_at DESC, id)` public index and partial trigram indexes for case-insensitive city/area search, built concurrently. The existing partial `(rental_mode, published_at DESC, id)` index and geography GiST index remain. `ST_Intersects(location, geography viewport)` and `ST_DWithin(location, point)` can use the geography index. Promotion predicates and varied filters can still require sorting; inspect plans on 10k, 50k and 100k fixtures before countrywide activation. Migration 0051 adds import scope fields and a disabled scope schedule table; it does not queue or crawl anything.

Search and map inputs have coordinate ranges, ordered bounds, at most 100 polygon vertices, at most 100 km radius, page limits and fixed marker/grid bounds. Spain coverage includes mainland, Balearic and Canary Islands, Ceuta and Melilla; the generic map is not restricted to Tenerife. Current Tenerife copy and default camera remain product defaults while nationwide inventory is disabled.

## External import work

Current source adapters and their Santa Cruz discovery URLs remain the only active crawl. The importer now reads known URLs in 250 URL chunks, fetches details in batches of 100 with per-source concurrency limits, commits each result, and checks stale records in 100 row keyset batches. Existing fingerprints skip unchanged rows and reconciled galleries. New imported galleries default to at most eight images; an existing larger gallery retains its count up to the previous 20 image ceiling. External videos are still never mirrored. Full and card/thumb variants are generated only when useful for source dimensions; cards request small variants and detail media is loaded on demand.

An operator can later configure province discovery slices in `external_import_scopes`. Rows are disabled by default and the environment gate `EXTERNAL_IMPORT_NATIONWIDE_ENABLED` is false. When both gates are enabled, the existing distributed import lock processes at most eight due slices per cycle. A slice has source, `province:<structured province name>`, provider-host HTTPS discovery URLs, interval, result and next run time. A crash leaves it due for an idempotent retry. The new province admission requires a structured source province and, if provided, a Spain country value; broad coordinate boxes or page navigation text are not sufficient. Provider-specific discovery routes and source data quality must be audited per province before enabling each row. Current Santa Cruz behavior is unchanged.

## Media, backup and reconciliation

User media limits remain 5–15 photos, one video, maximum 30 seconds. The external eight-image default is separate. Media asset keys and URLs are storage-backend agnostic, so a later move from local MinIO to compatible object storage does not change listing semantics.

`deploy-release.sh` continues to make an authenticated PostgreSQL backup, but checks for a recent authenticated MinIO archive instead of copying the entire bucket on every code release. Schedule `deploy/backup-minio.sh` separately at an interval that meets recovery objectives; the gate defaults to 72 hours. `deploy/prune-backups.sh` defaults to dry-run and only removes an expired archive when two newer authenticated archives of the same type exist. It holds the release lock. Verify restore drills and off-node copies before relying on local backup retention; keeping full media copies on the same disk scales approximately with bucket size times retained copy count.

`python -m app.commands.audit_media --limit 500` is a bounded dry-run audit. It classifies DB assets as `LIVE_REFERENCED`, `PENDING_DELETE`, `ORPHAN_CONFIRMED`, `DB_REFERENCE_MISSING_OBJECT` or `UNKNOWN`, emits JSON lines and a `nextAfter` cursor. Only an object with a deleted DB asset, no attachment and a confirmed object is eligible for `--enqueue-confirmed`. The deletion worker independently rechecks DB references immediately before storage I/O. Objects that exist only in the bucket are not classified by this DB-first audit and remain `UNKNOWN` until a separate bucket inventory is compared. Never infer deletion eligibility from a missing row alone.

Review Docker image and build-cache usage, container log sizes, backup directories, old release worktrees and temporary media routinely. The deployment code does not perform a blanket Docker prune or delete production data. Keep DB/MinIO volumes and off-node backups intact.

## Capacity model and rollout gates

The following is a *formula model*, not a byte forecast. Measure production `pg_total_relation_size`, index size, media objects by kind and backup compression before sizing the new node. Let `D` be average database bytes/listing including indexes, `E` be average stored bytes/external image including actual variants, `N` be average native media bytes/native listing, `f` be external listing share, `B` be the number of full media backup copies retained on-node, and `F` be fixed Docker/release/log/temp allocation. With the eight-image default, required disk is approximately `L × D + L × f × 8 × E × (1+B) + L × (1-f) × N × (1+B) + F + database backups`. Existing external galleries over eight must be measured separately.

| Listings (`L`) | External images at default | Database and indexes | Live media | Backups, Docker, logs, temp |
| ---: | ---: | --- | --- | --- |
| 10,000 | `80,000 × f` | `10,000 × D` | `10,000 × (8fE + (1-f)N)` | `B × live media + DB backups + F` |
| 50,000 | `400,000 × f` | `50,000 × D` | `50,000 × (8fE + (1-f)N)` | same formula |
| 100,000 | `800,000 × f` | `100,000 × D` | `100,000 × (8fE + (1-f)N)` | same formula |
| 250,000 | `2,000,000 × f` | `250,000 × D` | `250,000 × (8fE + (1-f)N)` | same formula |
| 500,000 | `4,000,000 × f` | `500,000 × D` | `500,000 × (8fE + (1-f)N)` | same formula |

Image processing currently targets 2048 px full, 960 px card and 480 px thumb WebP, so `E` must include only variants actually stored. Native listing media includes videos, so `N` cannot be inferred from image size. On a nominal 1 TB server, plan for no more than roughly 750–800 GB occupied to retain 20–25% free space. Six vCPU and 18 GB RAM is an initial node, not a guarantee of 500k-listing performance. Establish measured DB, media and backup values, query plans, import rate, CPU and disk write rate, restore time and free-space alerts before enlarging scope. Move media or backups off-node when the model approaches the reserve threshold.

## Observability and migration sequence

The API records search/map query duration, page/match counts and map marker/cluster counts with fixed metric labels. Import run duration/result and per-source counters already exist; scope completion logs include source, scope, result and counters. Storage deletion logs retain failures and live-asset guard events without high-cardinality Prometheus labels.

Deploy migrations and application code on the larger server after a verified PostgreSQL and MinIO restore drill. Confirm old public endpoints remain available during rolling deployment. Check search and map plans, API latency, counts and disk reserves with the current Tenerife dataset, then representative province slices, and only then increase active scopes. Do not turn on the nationwide gate or populate enabled scope rows as part of this PR. Redis coordinates locks and transient jobs; listing, source, run and scope state remains in PostgreSQL. Known risks are exact count cost, dense viewport aggregate cost, source-specific province coverage, and local media backup capacity. Mobile saved-first sorting sends at most 1,000 favorite IDs with a search request; larger saved sets need an authenticated server-side favorites join. Specialized sort plans need measurement before nationwide activation.
