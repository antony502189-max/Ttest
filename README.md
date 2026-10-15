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
- Paid promotion flows for listing TOP, a single homepage featured-listing slot, and up to seven advertising-banner slots. Stripe-hosted Checkout, payment orders, signed webhooks, reconciliation and administrator financial resolution are implemented in source; see [Payments](#payments-and-advertising).
- Admin Listings uses server-side search/filtering and incremental 50-row keyset pagination instead of loading the full catalog before showing results. See [admin performance](docs/admin-performance.md); historical benchmarks are **local synthetic**, not production timings.

## Architecture at a glance

```text
Browser (React 19, TypeScript, Vite, React Router HashRouter)
   │
   ├── Google Maps (browser API; restricted key)
   └── /api/v1 → FastAPI → SQLAlchemy async → PostgreSQL 16 / PostGIS
                          ├── Redis (rate limits / leases)
                          ├── MinIO (private S3-compatible media)
                          ├── mail-worker (SMTP outbox / reconciliation)
                          └── external-listings-worker (provider adapters)
               Payments API ↔ Stripe-hosted Checkout / signed webhooks
Public HTTPS: Traefik → frontend Nginx / API on Contabo VPS
```

Production is `https://app.112233.es` on VPS `169.58.147.65`. Existing Traefik is the public listener; Postgres, Redis and MinIO have no public host ports. The running release, enabled services and configured Stripe mode must be checked on the VPS; a merged feature does **not** establish that it is deployed or enabled. See [architecture](docs/architecture.md), [deployment](docs/deployment.md) and [operations](docs/production-operations.md).

## Payments and advertising

The source includes **Stripe Checkout** for three distinct purchases:

| Purchase | Current implementation | Fulfillment |
| --- | --- | --- |
| Listing TOP | A selected duration for a published listing | Activated/extended only after verified payment |
| Homepage featured listing | One shared featured-photo slot; one calendar month | Slot reserved for checkout; placement after verified payment |
| Advertising banners | Up to seven slots, with day-based campaigns and moderation | A paid banner enters administrative review; its approved period starts on approval |

Prices, eligibility and selected durations are calculated and validated on the backend. See [Stripe Checkout](docs/stripe-checkout.md) and [homepage advertising](docs/homepage-advertising.md) for the current product contracts; do not assume older screenshots or pricing fixtures are authoritative.

**Payment integrity:** the backend stores orders and separate fulfillment/financial status, verifies Stripe webhook signatures, can reconcile session status through the provider API, and supports audited administrative investigation of exceptional orders, refunds and disputes. A browser return to a success URL is **not** payment confirmation. Review the implementation and [payment audit notes](docs/payment-audit-fixes-2026-10-14.md); existing tests do not constitute a production or PCI certification.

**Mode and secret boundaries:**

- `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` are server-only secrets and must be configured together; never commit them or expose them through `VITE_*` variables.
- `STRIPE_LIVE_PAYMENTS_ENABLED` defaults to `false`; live-key checkout is gated and must be explicitly approved and configured.
- `STRIPE_TEST_PAYMENTS_ENABLED` also defaults to `false`. In production, enabling Checkout with `sk_test_` requires deliberate opt-in because **test purchases may grant real in-app promotional entitlements**.
- Never infer the active Stripe mode, payment readiness or webhook delivery from GitHub alone. Confirm deployed configuration without printing secrets, and verify provider events, refund/dispute handling and entitlement state before enabling paid services.

The webhook route is `POST /api/v1/payments/stripe/webhook`. Do not send real financial operations through local smoke tests. See [payment release compatibility](docs/payment-release-compatibility-2026-10-14.md) for migration/rollback constraints.

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

### Isolated Stripe testing (optional)

Use the **separate local Stripe sandbox**, not the production database or a public test-payment endpoint. The supported Windows procedure is in [Stripe local sandbox](docs/stripe-local-sandbox.md): configure Stripe CLI, create the ignored `.stripe-test.secrets` file with `scripts/set-stripe-test-secrets.ps1`, and then start `docker-compose.stripe-test.yml` with project name `ttest-stripe-test`. This stack uses a separate PostgreSQL volume and binds its test API to `127.0.0.1:18000`; do not use live Stripe keys or production customer data.

## Quality gates

```bash
npm run lint
npm run typecheck
npm run build
npm run test:e2e
npm run test:fullstack
npm run test:security
npm run test:bundle-security
```

For backend (Python environment installed with `pip install -e "backend[dev]"`):

```bash
cd backend
ruff check app tests
mypy app
pytest -q -m 'not integration'
```

The full infrastructure-backed audit is `bash scripts/final-audit-local.sh` on Linux/WSL. For focused admin regressions, use `npm run test:admin-performance` (the benchmark phase requires additional fixtures). GitHub Actions includes source snapshots, production/static audits, full audit, four-shard mobile Playwright, publication/auth validation and [payment audit](.github/workflows/payment-audit.yml) for payment-related changes. The payment workflow tests backend logic, real local PostgreSQL migrations/integration scenarios and mocked-provider browser flows; it does not make live Stripe charges. **Green CI is not a production smoke test or security certification.** [Testing handbook](docs/testing.md).

## Releasing safely

Changes go through a PR to protected `main`. On the correct VPS the controlled script is `deploy/deploy-release.sh <exact-40-character-origin-main-sha>`. It uses a release lock, validates immutable Git worktrees, checks a fresh MinIO backup, takes a PostgreSQL backup, applies migrations, deploys containers, verifies the public origin and rolls back the app if verification fails.

Before a payment-related release, review the Alembic compatibility baseline, verify the configured Stripe test/live mode and webhook event subscriptions, and ensure backups and rollback readiness. The normal release retains persistent data and does not switch payment mode on its own. The application rollback does not reverse financial transactions or downgrade migrations.

**Do not** run database cleanup, delete Docker volumes/backups/releases, run destructive migration scripts, bypass the lock, deploy an arbitrary older SHA or enable production payment flags without approval. Verify the active release and `https://app.112233.es/build-info.json` after deployment. [Release checklist](docs/release-checklist.md) · [Production operations](docs/production-operations.md) · [Monitoring](docs/production-monitoring.md).

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
| Payments, financial operations | [Stripe Checkout](docs/stripe-checkout.md), [Sandbox](docs/stripe-local-sandbox.md), [Payment audit](docs/payment-audit-fixes-2026-10-14.md) |
| Administrative performance | [Admin Listings performance](docs/admin-performance.md) |
| External imports | [External data](docs/external-import.md) |
| Production | [Deployment](docs/deployment.md), [Operations](docs/production-operations.md), [Troubleshooting](docs/troubleshooting.md) |

Historical implementation audits and research are retained in `docs/` for traceability. They describe their respective baselines and must not override current source code, workflows or runbooks.
