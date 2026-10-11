# 112233.es

Marketplace inmobiliario de alquiler en España / Spanish rental marketplace. **Vivienda** (long-term) and **Turismo** (holiday) are separate search and publication modes. Coverage includes mainland Spain, the Balearic Islands and the Canary Islands; the interface is not limited to Tenerife.

**Production application:** https://app.112233.es · **Repository:** https://github.com/antony502189-max/Ttest

> Source-of-truth rule: the GitHub `main` branch is the latest merged code, **not** proof that production runs that version. Read `/srv/112233.es/current` or the public `/build-info.json` to verify what is deployed. Production is the self-hosted VPS, **not GitHub Pages**.

## Capabilities

- Browse public property listings in scrolling cards and a Google Maps view; images, videos, favorites, discarded items, saved searches, notifications, account and owner publication flows.
- Mobile location picker covering **17 autonomous communities**: Spanish/Russian/English names, autocomplete against approximately 8,130 municipality names and catalog cities, region-specific published-listing counts, and regional scrolling results. Selecting `Barcelona` ranks **Cataluña** first; `comunidad=09` is the canonical region filter.
- Database-side geography filtering with PostGIS. `POST /api/v1/listings/regions/counts` uses the same published-visibility and other active search filters as card results.
- Map state: first visit shows an Atlantic overview of mainland Spain and the Canary Islands. Subsequent fresh visits use the last explored **virtual 70 km-radius zone**, fitted to the current screen; opening a listing is unnecessary. An exact map bookmark or returning via in-app Back is handled separately.
- Long-term listings obey the inclusive **€1,000/month** cap; the holiday mode has separate pricing rules and is **not removed or redirected**.
- Authenticated host publication, geocoding/address editing, moderated listings, commercial homepage campaigns, external-listing import, a transactional email outbox, and admin controls.

## Architecture at a glance

```text
Browser (React 19, TypeScript, Vite, React Router HashRouter)
   │
   ├── Google Maps (browser API; restricted key)
   └── /api/v1 → FastAPI → SQLAlchemy async → PostgreSQL 16 / PostGIS
                          ├── Redis (rate limits / leases)
                          ├── MinIO (private S3-compatible media)
                          ├── mail-worker (SMTP outbox)
                          └── external-listings-worker (provider adapters)
Public HTTPS: Traefik → frontend Nginx / API on Contabo VPS
```

Production is `https://app.112233.es` on VPS `169.58.147.65`. Existing Traefik is the public listener; Postgres, Redis and MinIO have no public host ports. See [architecture](docs/architecture.md), [deployment](docs/deployment.md) and [operations](docs/production-operations.md).

## Local quick start

Prerequisites: **Node.js 22+**, **npm**, **Docker Compose** and **Python 3.12+** for running the backend outside Docker. Docker Desktop is supported on Windows. Use only development credentials locally.

```bash
git clone https://github.com/antony502189-max/Ttest.git
cd Ttest
cp .env.example .env.local
npm ci
docker compose up -d postgres redis minio minio-init mailpit
docker compose up -d migrate backend mail-worker
npm run dev
```

PowerShell copy alternative: `Copy-Item .env.example .env.local`. Set `VITE_API_BASE_URL=http://localhost:8000/api/v1` (or your overridden backend port), `VITE_ENABLE_MOCK_MODE=0`. Vite prints its development URL, typically `http://localhost:5173`. Google Maps requires a browser-restricted key to use the real map. Mock mode `VITE_ENABLE_MOCK_MODE=1` is for isolated frontend tests only.

Optional local seed (development **only**):

```bash
docker compose --profile tools run --rm seed
```

Local endpoints: backend `http://localhost:8000`; interactive Swagger `http://localhost:8000/api/docs` (development only); Postgres `localhost:5432`; Redis `localhost:6379`; MinIO API/console `localhost:9000/9001`; Mailpit `http://localhost:8025`.

See [local development](docs/local-development.md) and [configuration](docs/configuration.md) for PowerShell commands, env variables, local services, fixtures and common failures.

## Quality gates

```bash
npm run lint
npm run typecheck
npm run build
npm run test:e2e
npm run test:fullstack
npm run test:security
```

For backend (Python environment installed with `pip install -e "backend[dev]"`):

```bash
cd backend
ruff check app tests
mypy app
pytest -q -m 'not integration'
```

The full infrastructure-backed audit is `bash scripts/final-audit-local.sh` on Linux/WSL. GitHub Actions independently runs snapshot, production/static audits, full audit, four-shard mobile Playwright and publication/auth validation. **A green CI result is not a production smoke test.** [Testing handbook](docs/testing.md).

## Releasing safely

Changes go through a PR to protected `main`. On the correct VPS the controlled script is `deploy/deploy-release.sh <exact-40-character-origin-main-sha>`. It uses a release lock, validates immutable Git worktrees, checks a fresh MinIO backup, takes a PostgreSQL backup, applies migrations, deploys containers, verifies the public origin and rolls back the app if verification fails.

**Do not** run database cleanup, delete Docker volumes/backups/releases, run destructive migration scripts, bypass the lock, or deploy an arbitrary older SHA. [Release checklist](docs/release-checklist.md) · [Production operations](docs/production-operations.md) · [Monitoring](docs/production-monitoring.md).

## Documentation index

Start with [the documentation hub](docs/index.md). Main references:

| Topic | Guide |
| --- | --- |
| Architecture, routes, state | [Architecture](docs/architecture.md), [Frontend](docs/frontend.md) |
| Geography & location picker | [Spanish communities](docs/spain-regional-search.md) |
| Map & visit history | [Maps and navigation](docs/navigation-and-maps.md) |
| API, auth, examples | [API reference](docs/api.md) |
| Database & migrations | [Database](docs/database.md) |
| Local setup, configuration | [Local development](docs/local-development.md), [Configuration](docs/configuration.md) |
| Tests, contribution | [Testing](docs/testing.md), [Contributing](docs/contributing.md) |
| Security & privacy | [Security](docs/security-and-privacy.md) |
| External imports | [External data](docs/external-import.md) |
| Production | [Deployment](docs/deployment.md), [Operations](docs/production-operations.md), [Troubleshooting](docs/troubleshooting.md) |

Historical implementation audits and research are retained in `docs/` for traceability. They describe their respective baselines and must not override current source code, workflows or runbooks.
