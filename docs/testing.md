# Testing and CI handbook

**Tests prove source contracts in isolated infrastructure. They do not prove what version is currently deployed or how many listings currently exist in production.**

## Frontend checks

Run at repository root:

```bash
npm ci
npm run lint
npm run typecheck
npm run build
npx playwright install chromium
npm run test:e2e
npm run test:a11y
npm run test:fullstack
npm run test:security
npm run test:bundle-security
```

`npm run test:e2e` runs the main Playwright suite plus publication and Google-auth configurations; `test:fullstack` requires actual backend, PostgreSQL/PostGIS and compatible local services. You can target focused tests:

```bash
npx playwright test tests/spain-community-search.spec.ts
npx playwright test tests/navigation-history.spec.ts
npx playwright test tests/mobile-location-map.spec.ts
```

The test fixtures and browser mocks are not the same as a live imported nationwide catalog. When a count equals zero under tests it does not establish live availability.

## Backend checks

From a Python 3.12+/3.13 environment with `pip install -e "backend[dev]"` and the appropriate test database:

```bash
cd backend
ruff check app tests
mypy app
pytest -q -m 'not integration'
pytest -q -m 'integration and not s3'
pytest -q -m s3
```

Integration tests require a live **PostgreSQL/PostGIS** database, not SQLite; S3 tests require disposable MinIO. Prefer `bash scripts/final-audit-local.sh` on Linux/WSL for a reproducible local pipeline: it creates a separate `ttest_test` DB, migrates it, lints/types/tests backend, runs frontend checks, real full-stack and mocked browser suites. It outputs diagnostics in ignored `output/`. It is intentionally **not a production-data test runner**.

## GitHub Actions

Workflows in `.github/workflows/` include:

| Workflow | Role |
| --- | --- |
| `audit-source-snapshot.yml` | Archive immutable tracked-source snapshot with checksum |
| `production-audit.yml` | Backend Ruff/Mypy, migration chain, PostGIS+MinIO integration; frontend lint/type/build/security/static serving |
| `mobile-validation.yml` | Four Chromium Playwright shards for mobile/E2E/a11y/visual plus publication/auth/search-lifecycle validation and a final `validate` job |
| `full-audit.yml` | Full local/a11y/full-stack audit and artifact collection |
| `update-visual-baselines.yml` | **Manual, reviewed** visual-baseline refresh only |
| `capacity-smoke.yml`, `external-source-contract.yml` | Capacity/source-contract checks as configured |

Required checks are enforced by branch policy. Do not infer a merge is safe until every required job for the **current PR HEAD SHA** is green. If a new fix changes the HEAD, all outstanding results of older commits are historical.

## Feature regressions

| Change | Minimum tests |
| --- | --- |
| Region picker / municipality matching | `tests/spain-community-search.spec.ts` and relevant i18n/location suites |
| Region spatial totals | `backend/tests/integration/test_autonomous_communities.py` |
| 70 km recall / map overlays / map URL | `tests/navigation-history.spec.ts`, map visual tests |
| Long/holiday cap & filters | `backend/tests/test_rental_price_limit.py`, corresponding E2E |
| External import and media integrity | integration fixtures, lifecycle/gallery and worker tests |
| Owner publication/video | publication Playwright configuration and backend upload-validation/media tests |
| Deployment/rollback | `scripts/check-production-config.sh`, deploy-safety/production-monitor tests |

## Visual baselines

Visual snapshots are pinned to a dedicated `visual-baselines` branch and installed by `scripts/install-visual-baselines.sh`. Normal CI must **not** update snapshots as a shortcut for red tests. Inspect expected/actual/diff screenshots and distinguish an intended product change from layout instability (e.g. map markers reloading). Only use **Update Approved Visual Baselines** after explicit visual review.

CI uploads Playwright HTML reports and failure artifacts. Keep captured user content, personal information, tokens and private production data **out** of test fixtures and artifacts.

## Pre-merge checklist

1. Identify relevant code/API surface and take a read-only baseline when the change involves data/config.
2. Add tests that assert user behavior rather than only implementation calls.
3. Run lint/typecheck/build; run backend unit + PostGIS integration for spatial changes.
4. Run mobile E2E, publication/auth when applicable, and visual comparisons.
5. Check that `main` still matches the PR base; merge through GitHub protections, never force-push `main`.
6. Documentation-only changes should still pass required CI; do not bypass red checks.
7. After release, separately run the **live** smoke check and verify `current` and `build-info.json`.

[Contributing](contributing.md) · [Release checklist](release-checklist.md) · [Troubleshooting](troubleshooting.md).
