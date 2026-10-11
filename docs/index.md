# Documentation hub — 112233.es

**Scope:** source code of `antony502189-max/Ttest` (reviewed 2026-10-11). This index points to current implementation contracts and retained historical reports. The protected `main` branch is the source of code truth. The running VPS release must be checked independently.

## Start here

| Audience | Read in order |
| --- | --- |
| New frontend developer | [README](../README.md) → [Local setup](local-development.md) → [Frontend](frontend.md) → [API](api.md) |
| Backend developer | [Architecture](architecture.md) → [Database](database.md) → [API](api.md) → [Testing](testing.md) |
| Map or location features | [Regional search](spain-regional-search.md) → [Maps](navigation-and-maps.md) → [Spain-scale architecture](spain-scale-architecture.md) |
| Production operator | [Deployment](deployment.md) → [Release checklist](release-checklist.md) → [Production operations](production-operations.md) → [Monitoring](production-monitoring.md) |
| Auditor or security reviewer | [Security](security-and-privacy.md) → [Testing](testing.md) → [Production runbook](production-operations.md) |
| Contributor | [Contributing](contributing.md) → [Testing](testing.md) → [Troubleshooting](troubleshooting.md) |

## Canonical current guides

- **Product and system:** [Architecture](architecture.md), [Frontend](frontend.md), [Regional search](spain-regional-search.md), [Map state](navigation-and-maps.md), [Spain-scale catalog](spain-scale-architecture.md).
- **Interfaces and data:** [REST API](api.md), [Database/migrations](database.md), [Configuration](configuration.md), [Security and privacy](security-and-privacy.md).
- **Building and validating:** [Local development](local-development.md), [Testing](testing.md), [Contribution workflow](contributing.md), [Troubleshooting](troubleshooting.md).
- **Operations:** [Deployment](deployment.md), [Release checklist](release-checklist.md), [Production operations](production-operations.md), [Read-only monitoring](production-monitoring.md), [External import](external-import.md), [Moderation](admin-moderation.md), [Homepage advertising](homepage-advertising.md).
- **Performance:** [Compression/caching](performance/compression-cache.md), [Mobile entry](performance/mobile-entry.md), [Publication chunk](performance/publication-route-chunk.md), [Capacity smoke](capacity-smoke.md).

## Feature implementation anchors

| Behavior | Code / test anchors |
| --- | --- |
| SPA routes & auth guards | `src/App.tsx`, `src/components/layout.tsx`, `src/api/auth.ts` |
| Mobile location UI | `src/components/mobile-app-v2.tsx` (`LocationScreen`) |
| Region names, aliases and boundaries | `src/lib/spain-communities.ts`, `src/data/{spain-communities,spanish-municipalities}.json` |
| API region counts and PostGIS filter | `backend/app/api/v1/listings.py`, `backend/app/repositories/listings.py`, `backend/app/spain_communities.py` |
| Map visit-history zones | `src/lib/map-visit-history.ts`, `src/components/map/results-map.tsx`, `src/components/mobile-map-listings-layer.tsx` |
| Listing publication & media | `src/pages/ListingCreatePage.tsx`, `backend/app/api/v1/{listings,uploads}.py` |
| External imports | `backend/app/workers/external_listings.py`, `backend/app/external_sources.py`, `docs/external-spain-parser-operations.md` |
| DB migration head | `backend/alembic/versions/0056_external_scope_checkpoint.py` |
| Production release | `deploy/deploy-release.sh`, `deploy/smoke-production.sh`, `deploy/rollback-release.sh` |

## Historical / superseded references

Documents with titles such as `final-audit.md`, `second-implementation-audit.md`, `test-report.md`, `frontend-freeze-report.md`, `external-*-review.md` and dated incident reports are **historical evidence**. Some describe the Tenerife-only rollout, old migration heads, past importer flags or an earlier GitHub Pages architecture. They remain for traceability, not as fresh operational instructions.

- [ADR 0001](adr/0001-backend-boundary.md): original separate-backend decision, superseded for production hosting.
- [ADR 0002](adr/0002-vps-production.md): current VPS/Nginx/Traefik deployment decision.
- [Long-term monthly cap](operations/long-term-rent-migration.md): policy and historical operator notes; live deployment script is authoritative for maintenance actions.

Never infer production catalog counts, import scopes, running SHA or available backups from a passing GitHub Action. Confirm them directly in the target environment, with approved read-only tools, before operating on user data.
