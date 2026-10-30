# Database, spatial model and migrations

## Current baseline

- **Production:** PostgreSQL 16 with PostGIS 3.4, persistent Docker volume. Redis and MinIO are independent stateful services.
- **Migration directory:** `backend/alembic/versions/`. Checked-in Alembic head as of 2026-10-30: **`0074_ai_saved_searches`**. `0032_media_reference_guard` remains the *frozen migration integrity baseline*.
- **ORM:** `backend/app/models/` and domain models; async SQLAlchemy 2 / asyncpg; PostGIS via GeoAlchemy2.
- **Schema contracts:** `backend/app/schemas/`; repository search in `backend/app/repositories/listings.py`.

Existing domains include account/session/reset/verification, `users`, `listings`, listing owner/contact fields, room details, images/videos/assets, favorite/discarded state, `saved_searches`, `search_history`, `listing_views`, promotions, notifications, moderation restrictions/audit, `mail_outbox`, external-import identities/scopes/checkpoints, commercial advertising, and cleanup/outbox state.

The private AI foundation adds typed fact batches and observations, source
generations, resolved search features, query proofs, durable quota/session/result
journals and registered saved-search snapshots. These additive tables do not
activate public AI, providers, ASR or notification delivery. See the
[architecture](architecture.md#private-ai-search-foundation) and
[query-proof contract](ai-search-developer/CURRENT_QUERY_PROOFS.md).

## Geographic behavior

`listings.location` is the **public listing map point**. Exact address/coordinates for a verified owner-created listing are held separately and require owner/admin permissions. Some external listings have only a source-provided public location or none; never infer an exact private location from an approximate marker.

- Published/visible listings are selected through `visible_query()`; price rules and moderation apply before exposure.
- `ListingSearchRequest.autonomousCommunity` adds a spatial predicate against one of 17 MultiPolygons loaded from `backend/app/spain_communities.json`; a 17-way case expression groups `POST /listings/regions/counts`.
- Card and map search share the region predicate, while the facet count endpoint drops only `query` and selected region so it can calculate **all** community counts for the remaining filters.
- Bounds/polygons/radius filtering uses PostGIS rather than client-supplied city labels; indexed geographic query plans and counts should be measured on nationwide datasets.
- Regional filtering requires a usable public map point. A record without coordinates is not silently placed in a community.

## Safe migrations and local commands

Create/update the **local development** database:

```bash
docker compose up -d postgres redis minio minio-init
docker compose up -d migrate
docker compose exec -T backend alembic current
```

The last command requires the backend service to be running; alternatively, inspect through `docker compose run --rm backend alembic current` after dependencies start. For direct Python dev:

```bash
cd backend
alembic upgrade head
alembic current
```

Local seeding is idempotent and **must not run in production**:

```bash
docker compose --profile tools run --rm seed
```

`docs/local-development.md` explains the two supported local approaches. Integration tests require a **real disposable PostgreSQL/PostGIS** database; SQLite is not supported for geography and migration acceptance.

## Migration governance

- Never edit, rename or squash applied migrations `0001`–`0032`. `scripts/check-migration-compatibility.py` enforces the frozen history.
- New revisions must be expand-only while previous production code remains a rollback target: avoid destructive row changes, column removal/renaming, incompatible constraints, type/default replacement and tightened nullability.
- A release applies migrations only from a verified immutable `origin/main` worktree, after stopping application writers and verifying backup prerequisites. **No ad hoc migration on a live production database.**
- Code deploys **do not** run global deduplication, gallery repair, record closure or physical media cleanup; those require a separate maintenance plan and explicit approval.
- CI migration tests are not evidence that current production data is healthy. Check actual migration head and backup status on the VPS before incident recovery.

## Backup and restore

Production backups are encrypted, checksummed and authenticated; the release verifies a sufficiently fresh MinIO archive and creates a PostgreSQL backup. Use `deploy/restore-verify.sh` and `deploy/restore-minio-verify.sh` for isolated restore drills before relying on recovery. The drill is **not** a request to overwrite the live database or bucket.

Use only the scripts and locks described in [Production operations](production-operations.md). Never run `docker compose down -v`, `docker volume prune`, or `docker system prune` on the production host.

See [API](api.md), [Regional search](spain-regional-search.md), [Operations](production-operations.md) and [Security](security-and-privacy.md).
