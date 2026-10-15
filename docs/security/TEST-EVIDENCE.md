# Verification evidence — 15 October 2026

All dynamic tests here use local synthetic records or mock provider responses.
No Stripe financial objects or production customer records were modified.
JUnit/scanner/browser output remains in ignored local `output/` and GitHub CI
artifacts where applicable; no production env file or credentials are included.

| Check | Observed result |
|---|---|
| Baseline Windows unit suite before source remediation | 724 passed, 3 skipped |
| Updated pinned Python 3.13/Linux unit suite | 753 passed, 3 skipped; 259 integration cases deselected |
| Updated Python 3.13/Linux Postgres/PostGIS + Redis integration | 258 passed; includes payments, deletion, ownership, refresh/session, moderation, media, schema and importer tests |
| Targeted Linux native video/HTTP/Checkout/Compose regressions | 42 passed, including real MP4/MOV/WebM and local decoy-server rejection |
| Final focused token/DNS/media/migration rerun | 40 passed, including the final five added time/purpose/DNS cases |
| Real isolated MinIO integration | One passed against the dedicated synthetic bucket |
| Migration static guard tests | Six passed; future constraint changes to released tables remain rejected |
| Migration governance after extending released freeze | Three passed; all 0057–0063 bytes match read-only production SHA-256 observations |
| Browser payment/advertising/homepage/TOP scenarios | 30 passed in Chromium against local app and mock API/provider |
| Frontend lint/typecheck/build | Passed; existing lint warnings and bundle-size warning remain |
| Production bundle and dependency policies | Passed |
| Backend Ruff/Mypy | Passed (108 application modules) |
| pip-audit 2.10.1 | Before: 17 advisories/two packages; after: zero |
| npm audit | Before: one high build dependency; after: zero |
| Bandit 1.9.4 baseline | Six low alerts / 20,532 source lines; no medium/high. Sentinel false positive and native subprocess boundary reviewed |
| Gitleaks 8.30.1 | All fetched branches: 3,801 commits / 31.67 MB; 51 generic matches in reviewed synthetic/public contexts. Current tracked source: 33 overlapping matches; no live service credential established |
| Production readiness and release identity | Healthy API; main/current/frontend SHA match; importer remains unhealthy |
| Latest production archive HMAC checks | Postgres PASS, MinIO PASS; no restore performed |

The initial integration run had 257 passing tests and one Redis test failure
because REDIS_URL was empty. That test passed on the dedicated Redis instance;
the complete pinned Linux integration rerun then passed all 258. Initial unit
collection lacked http-ece locally; installing the declared pinned pywebpush
test dependencies resolved collection. An early frontend command's unrelated
Ruff invocation used the wrong directory; backend Ruff was rerun correctly.
These were environment/invocation failures, not suppressed test failures.

Sanitized historical match context and fingerprints are in SECRET-SCAN-TRIAGE.csv.
Raw reports are fully redacted and remain local. Three existing unit skips are opt-in public route/source research and live
source-discovery smoke checks; they were not enabled against third-party sites.
Browser scenarios verify
the app/browser flows with synthetic API/provider behavior; they are not live
Stripe tests. Full visual/a11y/fullstack results must be read from
the final PR head's CI, not inferred from these 30 browser scenarios.

No aggressive DAST, unrestricted port scan, credential guessing, live financial
test, customer data export, production restore, kernel scanner, image Trivy
scan, independent human review, or provider-dashboard configuration check was
performed. No coverage percentage, production latency or incident-free period
is invented. See ASVS matrix for requirement-level limits.

## Reproduction

Use the constrained Linux Python 3.13 graph and disposable PostgreSQL/PostGIS,
Redis and MinIO. Tests truncate their test database and flush Redis DB 15;
**never point them at production**. Explicit isolated test DATABASE_URL and
TEST_DATABASE_URL are mandatory. Local audit used a dedicated Compose project
and loopback ports, without touching pre-existing local services.

```sh
python -m pip install --constraint backend/constraints.txt -e './backend[dev]'
cd backend
alembic upgrade head
pytest -q -m 'not integration'
pytest -q -m 'integration and not s3'
```

From repository root run migration guard/tests, frontend validation and the
existing payment browser command in `.github/workflows/payment-audit.yml`.
The new `security-audit.yml` only scans dependencies/static code and cannot
deploy. Existing required CI remains enabled; no baseline image was updated
and no test was skipped to obtain a green check.
