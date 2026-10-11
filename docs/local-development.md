# Local development (Linux, macOS, Windows/PowerShell)

This guide starts a **local development environment**, never production. Requirements: Node.js **22+**, npm, Docker/Compose, and Python **3.12+** when working directly with FastAPI. On Windows, use PowerShell and Docker Desktop; use WSL/Linux for `scripts/final-audit-local.sh`.

## Full-stack dev with Docker

```bash
git clone https://github.com/antony502189-max/Ttest.git
cd Ttest
cp .env.example .env.local
npm ci
docker compose up -d postgres redis minio minio-init mailpit
docker compose up -d migrate backend mail-worker
npm run dev
```

PowerShell instead of `cp`:

```powershell
Copy-Item .env.example .env.local
npm ci
docker compose up -d postgres redis minio minio-init mailpit
docker compose up -d migrate backend mail-worker
npm run dev
```

Configure `.env.local`: `VITE_API_BASE_URL=http://localhost:8000/api/v1` and `VITE_ENABLE_MOCK_MODE=0`. Google Maps requires `VITE_GOOGLE_MAPS_API_KEY` and `VITE_GOOGLE_MAPS_MAP_ID`; restrict the browser key to intended development/referrer origins. `VITE_GOOGLE_CLIENT_ID` is only needed when Google sign-in is configured.

If port 8000 is taken, set `BACKEND_PORT` for Compose and update `VITE_API_BASE_URL` to match. For example in PowerShell, run `$env:BACKEND_PORT="8001"` **before** starting the services.

## Local endpoints

| Service | URL / port | Notes |
| --- | --- | --- |
| Vite | displayed by `npm run dev`, normally `http://localhost:5173` | HashRouter routes under `/#/` |
| FastAPI | `http://localhost:8000` | `/health/ready`, `/api/v1` |
| Swagger (dev only) | `http://localhost:8000/api/docs` | Deliberately disabled in production |
| PostgreSQL/PostGIS | `localhost:5432` | local dev credentials from Compose |
| Redis | `localhost:6379` | local appendonly data |
| MinIO | `http://localhost:9000` | S3-compatible media API |
| MinIO console | `http://localhost:9001` | dev-only |
| Mailpit | `http://localhost:8025` | captures outgoing local mail |

To seed **only the local database**:

```bash
docker compose --profile tools run --rm seed
```

Seed data is mock/development content; never assume it is representative of the live Spain catalog. Development Compose also supports `external-listings-worker` when explicit source testing is intended. Do not enable or expand provider crawls or challenge circumvention just to validate the UI.

## Backend without Docker runtime

Use Docker for **Postgres/PostGIS, Redis and MinIO** while running FastAPI in your host Python environment. Run from repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e "backend[dev]"
cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

PowerShell activation: `.\.venv\Scripts\Activate.ps1`; backend environment is read from `backend/.env` copied from `backend/.env.example`. Ensure `DATABASE_URL` points to the running local Postgres and `STORAGE_BACKEND` matches your chosen local storage. The bundled Docker backend instead uses env keys defined in `docker-compose.yml`. Never paste VPS production secrets into a development env.

Development email is sent to Mailpit when using Compose. Direct backend execution needs correctly configured SMTP or a supported development logging route; do not assume sending succeeds just because API calls return 202. Local outbox worker:

```bash
docker compose up -d mail-worker
docker compose logs -f mail-worker
```

## Mock browser development

Set `VITE_ENABLE_MOCK_MODE=1` in `.env.local` only to exercise the fixture-backed UI. Production and real integration must use `0` and the FastAPI endpoints. If a search shows unexpected counts, first verify which mode is running. Real region counts come from `POST /listings/regions/counts`, while mock mode counts entries from fixture listings.

## Validate your change

```bash
npm run lint
npm run typecheck
npm run build
npx playwright test tests/spain-community-search.spec.ts
npx playwright test tests/navigation-history.spec.ts
```

For PostGIS/unit integration or full Playwright/a11y, use [Testing](testing.md). The full audit script creates `ttest_test`, migrates it, runs Python/static checks, starts test services and executes browser suites. It is **not** a deployment command.

## Common startup failures

- **No API listings / 404:** verify `VITE_API_BASE_URL`, Compose `backend` health, and actual `/api/v1` requests in DevTools Network.
- **Map blank:** check Maps key, allowed referrer, enabled APIs and browser console; API cannot substitute for Maps JS.
- **Database errors:** run `docker compose ps` and verify migration head with `alembic current`. SQLite cannot replace PostGIS.
- **Images fail:** check MinIO health, private bucket initialization and media URL. Do not make production buckets public.
- **Frontend shows demo data:** check `VITE_ENABLE_MOCK_MODE` and restart Vite after env change.

Full diagnostics: [Troubleshooting](troubleshooting.md). Safe production procedures: [Production operations](production-operations.md).
