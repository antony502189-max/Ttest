# System architecture

112233.es is a **React/TypeScript/Vite single-page application** served by Nginx, backed by a modular **FastAPI** service, asynchronous SQLAlchemy repositories and **PostgreSQL 16/PostGIS**. URL navigation uses React Router's `HashRouter`. Google Maps JavaScript API runs in the browser; the backend owns listing visibility and geography predicates.

```text
 Browser
  ├── React/Vite app, map, account, authoring & moderation UI
  └── /api/v1  ─────────────────────────────────────────────┐
                        HTTPS / Traefik → Nginx frontend    │
                         └── FastAPI routers  ←─────────────┘
                              ├── SQLAlchemy async → PostgreSQL + PostGIS
                              │                        └── Alembic 0001..0056
                              ├── Redis → rate limiting / distributed leases
                              ├── S3 storage adapter → private MinIO / assets
                              └── mail outbox → mail-worker → SMTP
                external-listings-worker → source adapters → PostgreSQL/media
```

## Boundaries

- `src/api/` is the browser's API transport and DTO mapping boundary; domain state and auth hydration live in `src/contexts/`. `src/App.tsx` defines guarded, lazy-loaded routes.
- `backend/app/api/v1/` holds HTTP routers, `schemas/` holds validated request/response DTOs, `repositories/` implements bounded SQL queries, `services/` owns domain rules, `models/` owns persistence, and `commands/` / `workers/` host background jobs.
- User listing data, saved searches, moderation state, notifications, external-source identity and history persisted server-side belong in Postgres; local map camera history and transient UI state are client-side and not a substitute for a saved search.
- Frontend routes use hashes such as `/#/buscar?... `; API URLs use direct paths `/api/v1/...`. Do not concatenate raw `#/...` values into API paths.
- `VITE_ENABLE_MOCK_MODE=1` is a testing mode with a fixture catalog. The production frontend builds with `0`, and bounded backend search/card/map calls drive the real listing feed.

## Public browsing

The production listing feed is **bounded**, not a full-catalog download. `POST /listings/search/cards` returns a page and an opaque cursor; `POST /listings/map` returns limited individual markers/clusters for the current viewport; detail and owner APIs remain separate. `GET /listings/catalog-version` supports change detection. `POST /listings/regions/counts` computes counts by the same visibility and region geography as search.

- **Long-term** (`rentalMode=long`): inclusive 1,000 EUR monthly ceiling. `holiday` is a distinct mode, with a nightly-rate model and independent UX.
- **Regional selection:** `comunidad=<01..17>` in the client URL maps to `autonomousCommunity` in API DTOs. PostGIS selects published listings in the requested autonomous community; a mere string match of the city name is insufficient.
- **Geographic sources:** simplified local region boundaries are used by the server and browser; browser also has an INE municipality dictionary for suggestions. [Detailed contract](spain-regional-search.md).
- **Maps:** the first mobile visit opens a broad Spain/Canary overview. Later fresh visits restore a virtual 70 km zone from browser storage, subject to explicit search/deep-link priority. No visible circles or new overlays are required. [Detailed lifecycle](navigation-and-maps.md).

## Security and data safety

The backend authenticates protected actions, applies permissions and moderation visibility at query time, enforces rate limits, validates geographic/price/media constraints and keeps admin authorization server-side. Access tokens are in memory; refresh session state uses HttpOnly cookies. Public map points are separate from owner/admin exact addresses and contact information.

Private media use an S3-compatible store (MinIO in production). Media workers normalize images/video; the transactional `mail_outbox` decouples sending from API requests. Import workers use bounded execution and per-source checkpoints; anonymous-scraping restrictions are respected.

See [Security](security-and-privacy.md), [Moderation](admin-moderation.md), [External imports](external-import.md), and [Database](database.md).

## Runtime / infrastructure

On the Contabo VPS `169.58.147.65`, source mirror `/srv/112233.es/repo` is separate from immutable Git worktrees `/srv/112233.es/releases/<sha>`. `current` points to the active release; the release script owns backup, migration, dependency-image guardrails, launch, public-origin verification and app rollback.

**No GitHub Pages production deployment.** GitHub Actions validate source. Only a release confirmed on the VPS is serving users. Do not bypass the deployment lock or run data maintenance as part of a normal code release. [Production operations](production-operations.md).

## Where to change things

| Change | Primary ownership | Required validation |
| --- | --- | --- |
| Location labels and city suggestions | `src/components/mobile-app-v2.tsx`, `src/lib/spain-communities.ts` | `tests/spain-community-search.spec.ts`, mobile E2E |
| Counts, filtering, map markers | `backend/app/repositories/listings.py`, request schemas | PostGIS integration tests, frontend E2E |
| Map recall radius/state | `src/lib/map-visit-history.ts`, map components | `tests/navigation-history.spec.ts`, map visual tests |
| Upload/publication | `backend/app/api/v1/uploads.py`, listing endpoints, publication UI | security and listing media contract tests |
| Migrations | `backend/alembic/versions/` | migration compatibility guard and PostGIS integration |
| Production service layout | `docker-compose.production.yml`, `deploy/` | `scripts/check-production-config.sh`, smoke verification |
