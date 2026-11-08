# PR411: remediation of the review at d2985d8

Scope: S2.1/S3/S6, A3/A5/A9/A11. Reviewed source:
`d2985d869c6af7e32d7791e605bc0113945190b4`, base main
`345b7ca80c1e2dd3853eaa7bbaf589ff8c17067a`. Same branch and PR411.
This report separates source/test readiness from deployment. **These review
changes have not been deployed. No real provider calls, production migrations,
snapshot exports/crawling, budget resets or production state writes were made.**
The earlier pilot remains on its earlier release and retained volumes/keys.

## Confirmation before changes

P1-01: the reviewed Nginx prefix forwarded every API path, and pilot.entry
imported app.main's global router tree. P1-02: Vite only replaced HomePage; the
ordinary App/main route tree and effects remained reachable. Both are confirmed
source exposures within the isolated pilot, not proof of access to primary DB.
P1-03: empty AIHTTPPolicy proxy trust necessarily selected the Nginx peer as
the IP bucket. P1-04: ordinary Vite base/API/mock fallbacks applied to pilot
mode; this was conditional on build inputs. P1-05: paid parse preceded candidate
eligibility, so an expired cohort could spend; occurrence depends on source age.
No exploit or paid reproduction against the live service was attempted.

## Remediation matrix

| Finding | Changed files / behavior | Proof | Status and residual limit |
| --- | --- | --- | --- |
| PR411-01 P1 | `backend/pilot/surface.py`, `entry.py`, `deploy/ai-site-pilot/nginx.conf`: minimal FastAPI, no app.main; explicit method/path allowlists at ASGI and Nginx. No auth/payment/listings/admin/upload/docs routers. Bearer headers are denied; Basic credentials stripped at Nginx. | ASGI deny tests; real sealed Nginx wrong-path/method assertions, unexpected-handler list remains empty; real PG mock-provider ASGI flow. | Fixed in source/tests. Requires separately approved deployment. |
| PR411-02 P1 | Dedicated `src/lab/site-pilot-main.tsx` entry/router; guest-only context, read-only card, no ordinary App/provider/global effects. Unsupported hashes redirect to the pilot. Ordinary entry remains unchanged. | Browser forbidden hashes, no account forms or nonpilot API; 93 ordinary AI/map/saved browser regressions. | Fixed in source/tests. Translation strings do not register routes. |
| PR411-03 P1 | Rendered exact Traefik peer; ingress rejected otherwise, sanitized rightmost XFF → X-Real-IP; backend trusts only fixed frontend 172.30.41.2/32. Compose static address and disjoint dynamic IP range. | Actual Traefik/Nginx/Redis clients .10/.11: A exhausted its bucket, B independently admitted; spoofed XFF/X-Real-IP cannot bypass; direct frontend denied. | Fixed/tested topology. Operator must verify peer/subnet before deployment; never trust a whole Docker network. |
| PR411-04 P1 | Vite enforces exact protected base/API and mock off, rejects contradictory env. `build-ai-site-pilot.mjs` requires clean Git and explicit peer, emits SHA/mode/file-hash manifest/rendered config/build.env. Frontend Dockerfile requires matching manifest SHA/mode. | Clean defaults + four wrong-env rejection cases, pilot build, emitted path scan. | Source implemented; exact committed build and CI result recorded below. No live release claimed. |
| PR411-05 P1 | Read-only `CatalogReadiness` uses existing visibility, current fact/card-value, source-health/age and proof predicates at budget ceiling. Runs before parser/key read and again immediately before transport/reserve. Status exposes catalog_ready/reason; UI blocks stale/unavailable. | Disposable real PG fresh→expired (original source timestamps aged beyond TTL), real TextSearchExecution release with zero business debit/reserve and zero provider reservations; mock-provider ASGI history read remains valid after expiry. | Fixed. This is readiness, not source refresh. Tiny post-check concurrency changes still face existing candidate validation. |
| PR411-06 P2 | No auth routers or forms in the pilot. Existing AI guest cookies remain Secure/HttpOnly/SameSite strict with rewritten pilot path. | ASGI auth URLs deny with no Set-Cookie; Nginx rewritten cookie/flags assertions; HTTPS-base ASGI guest identity test. | Fixed by removing the unnecessary auth surface. |
| PR411-07 P2 | Document logical namespacing only. Minimal entry removes marketplace storage effects; tests preserve favorites/draft/language/saved/media/continuation and computed third-party sentinels. | Desktop/mobile browser storage assertions and source import boundary. | Clarified/audited. Same-origin scripts can still access same-origin storage; strong origin isolation is not claimed. Separate origin remains a future decision. |
| PR411-08 P2 | Pilot-only input policy: 160 chars, matching positive grammar examples, immediate local hint/disabled submit on unsupported text. No location/pet invitation or legacy gallery recovery in pilot. Server fullmatch stays authoritative. | Browser valid/unsupported input tests; server negative tests and existing zero-debit flow. Ordinary UI keeps 16000-char/generic contract. | Fixed. Client hint is not a privacy certification or replacement for server gate. |
| PR411-09 P2 | Committed sealed Docker fixture and CI workflow; no host ports/live keys/socket, internal-only network. Real Nginx/Traefik/auth/cookie/IP tests, browser approved click→lost ACK same-key replay→refinement→reload, and real PG minimal-ASGI/mock-DeepSeek chain. | Network proof, browser suite, PG XML. Mock query counters distinguish replay from another interpretation. | Fixed via complementary layers. Sealed proxy fixture uses internal HTTP; fresh live HTTPS release acceptance still requires authorized deployment. |
| PR411-10 P2 | Recheck approval in transport and synchronous SQLite reserve guard. Operator `revoke.py` verifies exact container ownership, renames approval, then stops egress and always restarts backend, preserving journals. | Spawned external process removes approval between preflight/dispatch: no reserve/IO; mocked operator stop failure still restarts backend, counter bytes unchanged. | Fixed guard and procedure. File removal alone is not atomic network cancellation; already-dispatched usage cannot be refunded. Two-step revocation is mandatory. |
| PR411-11 P2 | Deterministic source selection constrained to card URL/text/amount, EUR/month/long, non-from price and current healthy source timestamp. LEFT JOIN exposes no-consistent-source explicitly; exporter refuses rather than overwriting card price. | Real PG two-source reversed-recency/different-price fixture selects matching source; changing attribution to inconsistent pair gives explicit null/refusal. | Fixed. A cohort with no consistent source fails closed, which can reduce availability until data is corrected. |
| PR411-12 P2 | Timestamp/source-of-truth labels in README and this report. Historical four-call run retained separately from later seven-call owner test. | Authenticated read-only status 2026-11-08T18:45:10Z:7/50, approved=true/halted=false, zero calls by observation. | Fixed documentation; counters are observations, not a live promise. Never infer/reset journal. |
| PR411-13 P2 | Exact-head CI must complete before requesting approval. Older evidence is indexed as historical, not new certification; no retention evidence deleted or branch history rewritten. | Current-source CI/provenance snapshot to be appended after checks. | CI pending at initial source commit. Remains open until mandatory workflows pass. |

## Validation and failures

Local:77 focused backend tests PASS;11 pilot browser cases PASS;93 ordinary
AI/map/saved browser cases PASS; mypy175 app files PASS, tsc/build, Ruff and
i18n guard PASS. Oxlint has only six existing unrelated warnings. New dedicated
build contract accepts clean safe defaults and rejects four contradictory envs.
Real PostGIS: expiry/zero-debit and reversed-source selection2 PASS; complete
minimal-ASGI/real-PG/mock-DeepSeek/replay/refinement/map/expired-history1 PASS.
Full seed/recovery suite and exact-head CI results are recorded after completion.
Counts overlap broader CI; do not add them as unique total cases.

Initial harness failures were retained outside the live service and corrected:
the duplicate-source fixture initially violated the real unique URL constraint;
an assertion initially treated a serialized failure code as enum; a dynamic
Redis IP collided with the fixed frontend test IP; Nginx required quoted regex
quantifiers. The accepted final proxy run and PG tests pass after correction.
These are not failed paid requests or edits of real data. An incorrectly escaped
test-run shell command stopped before starting infrastructure; it was replaced
with a structured script argument. Full raw temporary harness logs remain in
`/srv/112233-ai-review-411-20261108` and ignored `output/pr411-review`.

## Provenance and archived evidence scope

`git diff d2985d8..HEAD` is the remediation-only projection. PR411 also contains
older owned final reports from PR409/410 and PR404 provenance documents. Those
were preserved before switching the shared worktree to this branch, and are
archival prerequisites, not new runtime implementation or current acceptance.
The immutable historical evidence verifier explicitly reports whether old
container evidence applies to current source; that remains false. Current
runtime-input manifest includes all tracked runtime trees and new test/build
files. No old XML/report/journal was deleted to make the diff look smaller.
Review runtime changes in `backend/pilot`, the selected seeder/export tests,
`deploy/ai-site-pilot`, `src/lab`, the optional shared dialog input policy, Vite,
and the dedicated build/test workflows; review current proof in
`pr411-remediation-20261108-evidence`. Other old evidence is historical context.

## Rollback and deployment boundary

No deployment was performed. Existing running services, original production
DB0066, sealed three-call demo, provider/erasure journals, signing keys and
restricted catalog remain in place. New fixed network/manifest/minimal API must
be released together only after review and separate authorization. Before that
release, save current DB/state and provider checkpoint; use the same volumes and
approval binding. Network recreation must never use down-v or replace keys or
source timestamps. File revocation plus owned egress stop/backend restart is
mandatory to terminate in-flight work; preserve every reservation. Rollback
restores only prior images/config/network after revocation, retaining the newest
durable state. Full product/provider/account/data/performance/voice/saved/delivery
gates remain open. No automatic merge or public rollout.
