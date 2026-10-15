# Security integration with the approved PR #347 interface

This integration starts at `origin/main` commit
`6689c8261d436e5c5fc930dc9375c4fefb51bdf6`, which merged #347. PRs #345 and
#346 were still open at inspection; #348 did not exist. The default branch is
`main`. No later integration PR appeared in the repository's recent PR list.

The #346 head `2f331d502fa23888ccb35f5151ecda347098dcc6` contains #345's
`ab1867a22072ab3a1064b3234401d60dfceee7d1`. A single non-fast-forward merge
preserves their four commits once, on a branch created from current main.
There were no textual conflicts. No React source, CSS, public assets, font,
layout, translation, or existing migration file changed relative to main.
Only browser test coverage was extended. Existing untracked sandbox audit
files in the user's checkout were excluded from the commit.

## Additional verified defects and fixes

| Priority | Defect / root cause | Correction | Regression evidence |
|---|---|---|---|
| P2 | Python `is_global` includes multicast, so the shared outbound policy accepted IPv4/IPv6 multicast DNS answers | Also reject `is_multicast` before opening a socket | Four synthetic DNS cases assert no socket call |
| P2 | Connection-time DNS could wait indefinitely when an HTTPX caller set `timeout=None` | Independently apply the five-second DNS deadline, retaining the caller's overall connect timeout | A slow synthetic resolver times out even with client timeouts disabled; no socket call |
| P2 | Unsigned webhook timestamp larger than float range raised `OverflowError` before HMAC validation | Use integral timestamp comparison; retain the five-minute tolerance and constant-time HMAC check | A 400-digit timestamp returns HTTP 400 |
| P2 | Checkout response parsing assumed an object and accepted non-string session IDs/URLs | Require an object with nonempty string ID and URL, otherwise HTTP 502 | Null/list/string/wrong-field-type provider fixtures |
| P3 | Financial event parsing called `.get` on malformed `data` | Validate the event envelope before provider or transaction work | Null/list/string event data returns HTTP 400 with no provider call/commit |

`backend/tests/test_security_integration_boundaries.py` reproduces these
boundaries using synthetic data. Before the first fixes, 11 of the initial
12 cases failed. All 13 final cases pass. This is validation hardening, not
evidence that Stripe's real provider has returned malformed data or that
multicast TCP exploitation occurred in production.

HTTPX's network-backend injection remains private API. `constraints.txt` pins
HTTPX 0.28.1 / HTTPcore 1.0.9; project metadata now also bounds HTTPX below
0.29 and HTTPcore below 1.1. Existing real-pool synthetic socket tests verify
IP-literal connections, original TLS SNI/Host, private/mixed DNS rejection and
proxy denial. Replacing the HTTPX transport adapter wholesale would increase
scope and compatibility risk; review these tests whenever lifting the bounds.

## Payment and interface review

Checkout ownership, server pricing, advisory locks, idempotency keys, provider
expiry before releasing inventory, duplicate-event fulfillment and financial
inbox replay remain in their existing shared paths. Browser redirects do not
fulfill orders. Disabled production test purchases fail before new order
persistence. Existing orders can still reconcile; enabling payments or changing
that operational policy is outside this integration.

The seven-banner limit and vacancy slide, explicit payment confirmation,
listing-specific promotion selection and 10–365 day calendar remain unchanged.
Calendar dates select a number of paid days: actual activation follows verified
payment, and existing TOP receives an extension. They do not promise a fixed
expiry independently of payment timing. New tests cover all four duration
presets across year boundaries in UTC, America/Los_Angeles and
Pacific/Kiritimati, plus empty-date rejection. Existing tests cover Madrid DST,
leap years, desktop/narrow mobile and Russian/English/Spanish flows.

The Payment audit browser job now explicitly includes the owner flow and calendar
tests, in addition to their existing inclusion in Mobile validation. Both backend
CI jobs explicitly install and check FFmpeg/FFprobe so MP4/MOV/WebM normalization
and disguised-playlist network rejection are actually executed there.

## Executed local verification

Windows Python 3.12.14 used `output/release-venv/Scripts/python.exe`; Node used
the local Node 24 runtime. Linux Python 3.13 and Node 22 remain the authoritative
constrained CI environments. All tests use synthetic/local settings.

| Executed command (from backend unless otherwise stated) | Result |
|---|---|
| `python -m pytest -q -m 'not integration' --junitxml=../output/security-integration-unit.xml` | 762 passed, 7 skipped, 259 integration cases deselected |
| `python -m ruff check app tests` | Passed |
| `python -m mypy app` | Passed, 108 modules |
| `python -m pip check` | Passed |
| root: `python scripts/check-migration-compatibility.py` | Passed; all released hashes verified |
| root: `python scripts/test-migration-compatibility.py` | Six passed |
| root: `python scripts/check-supply-chain.py` | Passed |
| root: `python -m pip_audit -r backend/constraints.txt --no-deps --disable-pip --format json --output output/security-integration-pip-audit.json` | Zero known vulnerabilities |
| root: `python -m bandit -r backend/app -ll` | Zero medium/high; six low findings retained for review |
| root: `npm audit --audit-level=moderate` | Zero vulnerabilities |
| root: `npm run test:security` | Passed |
| root: `npm run lint`, `npm run typecheck`, `npm run build`, `npm run test:bundle-security` | Passed; existing warnings retained |

The seven unit skips are three existing opt-in external-source checks and four
native FFmpeg cases (binaries absent locally). Docker's Linux daemon is not
running, so PostgreSQL/PostGIS/Redis/MinIO and full-stack suites were not run
locally. Their results, browser/visual/accessibility outcomes and final-head CI
run links are recorded in the integration PR. Earlier #345/#346 CI is historical
evidence and is not counted as this branch's final verification.

Initial local attempts encountered sandbox network restrictions, stale local
dependency versions, a Windows native-module lock during `npm ci`, and missing
Chromium. Networked installs with appropriate sandbox permissions updated the
specified Python patches, restored npm modules without lockfile changes and
installed matching Chromium. No assertion was removed and no baseline image
was regenerated. Clean Linux `npm ci` is still required by CI.

The GitHub connection can read PRs/actions and push changes, but branch-protection
administration returned HTTP 403. Therefore the exact current protected-check
configuration was not independently verified; inspect all checks on the final PR
head rather than inventing a required-check list.

## Remaining risk and deployment boundary

The inherited security reports describe an earlier read-only production audit.
They are historical observations, not a fresh inspection of production in this
integration. No production connection, deployment, migration, payment, refund,
credential rotation or host change was performed here.

All inherited open findings remain open pending separate verification/remediation:
runtime PostgreSQL superuser (SEC-001), administrative SSH (006), backup/restore
and offsite continuity (008), CSP (009), importer health (010), Docker API
authority (012), Chromium egress (013), and administrator MFA (014). See
FINDINGS-REGISTER.md for original evidence and confidence levels. Configuration
changes do not establish production remediation. No fresh history-wide secret
scan, host/image scan, restore drill or independent ASVS certification is claimed.

Chromium's DNS preflight still precedes Chromium's independent DNS/socket use.
HTTPX hardening does not close that gap. Rebinding remains an unverified browser
risk requiring a synthetic browser harness and separately rehearsed egress proxy
or network isolation denying loopback/private/link-local/metadata/data networks,
including redirects, subresources and alternate protocols. Routing checks,
blocked service workers and blocked WebSockets are retained. A transparent
HTTPX fetch replacement is not safe to introduce without source/cookie/browser
compatibility evidence. Do not claim Chromium connection pinning.

FFmpeg accepts self-contained container formats and denies playlist/network
inputs; it is still a native decoder, not an OS filesystem/CPU sandbox. Keep
upload/process limits and container isolation; broader decoder fuzzing and
uncommon codec/container combinations have not been exhaustively certified.

Log rotation changes Compose configuration hashes and may recreate PostgreSQL,
Redis and MinIO along with application services during an eventual deployment.
Rehearse recovery and obtain a stateful-service maintenance window. No migration
DDL or stateful image changes are introduced. Keep both Stripe activation flags
false unless separately approved. The earlier sequential #345/#346 merge plan is
superseded by this single integration PR; merge/deploy only the reviewed result
after human approval and current release/backup checks, never an old hardcoded
rollback SHA without revalidation. No auto-merge is enabled.
