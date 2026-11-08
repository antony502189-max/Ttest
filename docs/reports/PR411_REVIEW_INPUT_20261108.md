# Code review PR #411 — AI Search Site Pilot

**Repository:** https://github.com/antony502189-max/Ttest  
**PR:** https://github.com/antony502189-max/Ttest/pull/411  
**Reviewed HEAD:** `d2985d869c6af7e32d7791e605bc0113945190b4`  
**Base:** `345b7ca80c1e2dd3853eaa7bbaf589ff8c17067a` (`main`)  
**Date:** 2026-11-08  
**Volume:** 10 commits, 81 changed files, +5,566/−33 lines. **Status at inspection:** OPEN / DRAFT / mergeable.

## Verdict

**REQUEST CHANGES. Do not merge until the P1 findings are addressed or explicitly accepted by the owner with narrowly defined compensating controls.** The pilot has real HTTPS/provider evidence, and the tests cover several important functional paths; this is not a claim that the whole pilot is nonfunctional. The review is a static review of GitHub sources, PR metadata, CI statuses and checked-in evidence. **No paid DeepSeek calls, production requests, deployment, direct VPS inspection, or local end-to-end runtime tests were performed during this review.** Findings below distinguish confirmed code-level behavior from conditional risk. GitHub Actions status is a point-in-time observation and must be rechecked before merging.

## P1 — must fix before merge

### PR411-01 — The pilot reverse proxy exposes the entire application API instead of an AI-only allowlist

**Confidence:** confirmed by routing code; exploitability of each individual non-AI route depends on its own permissions/configuration.

**Code:** [nginx.conf L16–L28](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/deploy/ai-site-pilot/nginx.conf#L16-L28), [pilot.entry.py L59–L63](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/backend/pilot/entry.py#L59-L63), [app.main.py L428–L449](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/backend/app/main.py#L428-L449).

`location /ai-pilot/api/` rewrites and forwards **every** URL under this prefix. `pilot.entry` imports the global `app`, which registers `/api/v1/auth`, `/api/v1/listings`, `/api/v1/payments`, `/api/v1/admin`, `/api/v1/uploads` and other routers. HTTP Basic only restricts who may call them; it is **not** an AI-route allowlist. For example, `/ai-pilot/api/v1/auth/register` is forwarded to the real registration route in the isolated test database. This conflicts with the promised narrow owner/team *rental-only* pilot surface, permits unneeded write/state paths, and dramatically increases audit scope. **Do not claim that these paths reach the ordinary production database:** the reviewed Compose points to a separate PostGIS database; the issue is unnecessary exposure and potential mutation of the pilot environment.

**Fix:** allow only the exact AI endpoints/methods required by the pilot and `/api/v1/private-demo/status`, or instantiate a dedicated minimal FastAPI application with only those routers. Deny `/auth`, `/payments`, `/listings` write paths, admin, uploads, `/api/docs`, `/api/openapi.json` and unexpected paths. Add real Nginx/ASGI integration assertions that non-AI URLs return 403/404 before handler execution, while session/query/result/map endpoints still work.

### PR411-02 — The frontend build still includes the normal marketplace routes, not only the pilot

**Confidence:** confirmed by source route tree.

**Code:** [src/App.tsx L1–L47 and route tree](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/src/App.tsx), [vite.config.ts sitePilot alias](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/vite.config.ts), [site-pilot-home.tsx](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/src/lab/site-pilot-home.tsx).

Site mode substitutes only the HomePage import and some UI behavior; the `HashRouter` still offers `#/registro`, `#/acceso`, `#/publicar`, `#/publicidad/...`, `#/admin`, etc. A user can navigate to these routes within the Basic-protected pilot. Even if API write paths are blocked after fixing #01, the pilot still shows misleading controls and may trigger unexpected calls. The source tree loads normal app providers and global effects rather than a minimal pilot composition.

**Fix:** add a dedicated pilot-only entry/router/layout or an explicit mode-gated route tree whose only allowed navigation is the AI pilot. Hide normal publish/login/payment/admin controls. Verify navigation to all forbidden hashes neither renders an operational form nor makes a nonpilot API call. Preserve ordinary site's route tree unchanged.

### PR411-03 — All browser users may share a single reverse-proxy IP quota

**Confidence:** confirmed code behavior, subject to the network topology documented in Compose.

**Code:** [entry.py AIHTTPPolicy](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/backend/pilot/entry.py#L83-L94), [ai_http_policy.py L31–L38](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/backend/app/services/ai_http_policy.py#L31-L38), [ai_search.py IP gate](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/backend/app/api/v1/ai_search.py#L225-L229), [ai_operating_limits.py](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/backend/app/services/ai_operating_limits.py), [nginx.conf](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/deploy/ai-site-pilot/nginx.conf).

Pilot config uses `AIHTTPPolicy(20, 3, (), ORIGIN)`, with an **empty trusted proxy network list**. `AIHTTPPolicy.address()` thus returns `request.client.host` and ignores proxy headers. In this deployment backend sees **Nginx's internal IP**, not each browser's real address. This collapses `ai-http`, `ai-guest-issue` (2/minute, 10/hour) and IP attempt budgets into common buckets: one tester can rate-limit another without either exceeding their own quota.

**Fix:** define a precise trusted reverse-proxy topology. Nginx must take the real client IP only from a verified trusted Traefik ingress (not from arbitrary client-supplied `X-Real-IP`/`X-Forwarded-For`), set a sanitized header to backend, and configure `AIHTTPPolicy.trusted_proxy_networks` narrowly. Alternatively use authenticated tester identities for those budgets. Test two real client IPs via Traefik→Nginx→backend, spoofed forwarded headers, and independent quota enforcement. Do **not** simply trust all Docker subnet addresses or arbitrary headers.

### PR411-04 — Site build-mode protections depend on undocumented environment variables rather than failing closed

**Confidence:** confirmed source-level fallback; *conditional* on a misconfigured build (the checked-in offline preview sets the values correctly).

**Code:** [vite.config.ts mode/base/config](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/vite.config.ts), [src/api/client.ts L1](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/src/api/client.ts#L1), [scripts/serve-ai-site-pilot.mjs](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/scripts/serve-ai-site-pilot.mjs).

The offline preview forcibly sets `VITE_BASE_PATH=/ai-pilot/`, `VITE_API_BASE_URL=/ai-pilot/api/v1`, `VITE_ENABLE_MOCK_MODE=0`; `vite.config.ts` itself does not require those values for `mode=ai-site-pilot`. A normal `vite build --mode ai-site-pilot` in a clean/misconfigured environment can silently compile root-based assets and `/api/v1` requests instead of protected `/ai-pilot/...`, and can inherit mock mode. Because the pilot shares a host with the ordinary site, wrong API origin/path is a high-impact deployment error.

**Fix:** for `sitePilot`, enforce exact base path/API prefix and mock-mode disabled *inside the build configuration*; reject any contradictory environment input. Create a single reproducible production pilot build command that writes a manifest with the exact SHA and mode. Verify emitted JS contains only pilot API prefix, and deployed asset requests never reach root `/assets` or ordinary `/api/v1`. Include a deliberate wrong-env build rejection test.

### PR411-05 — Model spending can continue after the fixed source snapshot becomes stale

**Confidence:** confirmed ordering and 24-hour policy; occurrence is time/data dependent.

**Code:** [entry.py parser/readiness](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/backend/pilot/entry.py), [demo.entry.py pipeline 86400s](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/backend/demo/entry.py), [ai_search_execution.py L164–L179](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/backend/app/services/ai_search_execution.py#L164-L179), [ai_fact_quality.py L24–L41](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/backend/app/repositories/ai_fact_quality.py#L24-L41), [report](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/docs/reports/AI_SEARCH_SITE_PILOT_20261108.md).

The pipeline parses via paid DeepSeek **before** `query_candidate()` checks source freshness. The 13-listing corpus is a non-refreshing snapshot; source freshness uses 86,400 seconds from the source's last successful observation. Once proofs/sources age out, the frontend can still show approved/unhalted and submit; dispatch may be billed only to end with zero results or coverage failure. This is not an allegation that the snapshot is already stale at review time.

**Fix:** introduce read-only pre-dispatch catalog readiness/eligibility and expose it in pilot status. For a fully expired/ineligible cohort, block **before** model transport/budget reserve, returning a distinct `PILOT_CATALOG_STALE`/`SOURCE_COVERAGE_UNAVAILABLE` to the UI. Respect original source timestamps: no fake timestamp refresh or unauthorized scraping. Test time travel past policy TTL: calls and quota consumption must remain zero; historical result reads should remain possible if retention allows.

## P2 — reliability, UX, tests, and acceptance

### PR411-06 — Auth endpoints can issue non-`Secure` refresh cookies in pilot test environment

**Confidence:** confirmed conditional route behavior; depends on calling auth flow exposed by #01.

**Code:** [compose.yml APP_ENV=test](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/deploy/ai-site-pilot/compose.yml), [auth.py `secure=settings.is_production`](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/backend/app/api/v1/auth.py#L35-L49), [nginx.conf proxy_cookie_path](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/deploy/ai-site-pilot/nginx.conf).

`APP_ENV=test` sets `secure=False` on refresh cookies in the normal auth routes. Because #01 exposes those routes through HTTPS pilot, a tester using registration/login can receive a non-`Secure` cookie. Prefer removing auth endpoints entirely from the pilot; if kept by explicit policy, make cookies secure based on HTTPS public-facing deployment, not just production mode, and test path rewriting, `Secure`, `HttpOnly`, and `SameSite`.

### PR411-07 — `app.112233.es` namespace separation is not a browser security boundary

**Confidence:** architectural limitation, not an observed cross-site data leak.

**Code:** [vite.config.ts replacement of `112233:`](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/vite.config.ts), [compose.yml host](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/deploy/ai-site-pilot/compose.yml).

Replacing literal `112233:` in src code provides useful namespacing for *known* keys, but both pilot and ordinary site are under the same HTTPS origin. Scripts with access to that origin can read/write the same origin-scoped `localStorage`/`sessionStorage`, regardless of key naming; Basic also does not provide origin isolation. Treat claims as **logical namespace isolation**, not security isolation. For strong browser isolation, use a dedicated subdomain/origin plus appropriately scoped cookies. If keeping same origin, audit all storage/cookie names, especially computed and third-party keys, and test no modification of ordinary keys beyond one favorites sentinel.

### PR411-08 — UI invites arbitrary requests, backend accepts only a 160-character strict rent grammar

**Confidence:** confirmed mismatch in client and backend constraints.

**Code:** [home-ai-search.tsx textarea maxLength=16000 and generic placeholder](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/src/components/home-ai-search.tsx), [pilot/input.py 160 chars/fullmatch](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/backend/pilot/input.py), [pilot home](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/src/lab/site-pilot-home.tsx).

Global AI component suggests location, residents, pets etc. The pilot gate accepts only tightly formatted monthly price/clear-budget utterances and rejects strings longer than 160. The dialog still allows 16,000 characters. The extra pilot banner helps, but the submit flow gives generic unsupported notices and no immediate explanation. Scope a pilot-specific client validator/hints and textarea length; keep server fullmatch authoritative. For rejected text, show allowed examples and test zero provider dispatch/zero business quota debit. Do not change the ordinary UI contract.

### PR411-09 — Browser contracts do not test real HTTP Basic/Nginx or approved model request lifecycle

**Confidence:** confirmed by test setup, not a claim live manual proofs are false.

**Code:** [tests/ai-site-pilot.spec.ts](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/tests/ai-site-pilot.spec.ts), [playwright config](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/playwright.ai-site-pilot.config.ts), [workflow](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/.github/workflows/ai-search-frontend.yml).

The eight browser cases use Vite preview and intercepted status/API responses. The `approved` case tests an enabled submit button but **never clicks it**; `paid=[]` only establishes that no request was sent. There is no committed reproducible reverse-proxy integration suite proving Basic 401, API allowlist denial, rewritten cookies, idempotent retries, or actual Nginx/CSP behavior; evidence of some real HTTPS manual testing is present separately. Add a sealed dockerized test composition with mock provider and exact Nginx route verification, plus an approved click -> mock query -> refinement -> reload test with zero external model calls. Keep live paid smoke explicitly opt-in and out of CI.

### PR411-10 — Pilot status and approval revocation are not an atomic dispatch kill switch

**Confidence:** source-level operational race, bounded by the provider/client timeout.

**Code:** [entry.py approved()/parse](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/backend/pilot/entry.py), [README rollback sequence](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/deploy/ai-site-pilot/README.md).

`approved()` is checked before parsing, while `reserve()` and CONNECT are later stages; removing approval file alone does not synchronously stop an already-approved in-flight request. The README correctly includes stopping egress/restarting backend; this should be considered part of mandatory revocation, not a standalone file kill switch. Add a process-level test with approval removal between preflight and transport, plus a documented fail-closed two-step rollback with journal preservation and in-flight caveats. Consider checking approval again directly before budget reserve if an atomic proof is practical.

### PR411-11 — Deterministic selected source is not required to match the listing's advertised price

**Confidence:** conditional data-quality/availability issue; the current 13-row snapshot was reported as valid.

**Code:** [deploy/ai-text-demo/export_public.py L21–L38](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/deploy/ai-text-demo/export_public.py#L21-L38), [seed_state.py validated_snapshot](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/backend/demo/seed_state.py).

The new `JOIN LATERAL` chooses latest-success active PisoCompartido source per listing, but doesn't prove it is the source corresponding to `l.monthly_price` and normalized price facts. With multiple active sources having differing prices, export can select an inconsistent pair, then the seeder rejects the entire snapshot. This is a **fail-closed availability problem, not demonstrated wrong priced cards**. Add fixture with two sources (different amounts/timestamps) and define deterministic selection constrained by price consistency, source proof and recency; do not silently overwrite listing price. Preserve source attribution and fail explicitly if none valid.

### PR411-12 — PR description and committed documentation disagree on remaining provider attempts

**Confidence:** confirmed stale evidence, not code defect.

**Code:** [PR #411 body](https://github.com/antony502189-max/Ttest/pull/411) states latest owner-test counter **7/50**; [pilot report](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/docs/reports/AI_SEARCH_SITE_PILOT_20261108.md) and [deployment README](https://github.com/antony502189-max/Ttest/blob/d2985d869c6af7e32d7791e605bc0113945190b4/deploy/ai-site-pilot/README.md) still show **4/50**.

Those can both be valid historical snapshots, but README currently phrases 4/50 as active status. Label all counters with observation timestamp and source of truth; distinguish historical 4 from later 7. Do not edit/reset journal or infer current budget by addition/subtraction. Obtain actual current status via read-only source-of-truth check with credentials redacted.

### PR411-13 — Current HEAD CI is not yet fully green and PR contains extensive unrelated evidence

**Confidence:** confirmed at review observation, may change.

At inspection, current HEAD check-runs: **13 successful, 2 conditionally skipped, 5 in progress, 0 failed**. In-progress jobs: backend-production, facts-postgres, and 3 mobile mock-e2e shards. Do not treat earlier commit CI as proof of this HEAD. Re-query all checks before approving. Further, PR includes previous PR409/410 and PR404 reports/evidence and an oversized XML history; separate archival housekeeping from the new pilot when safe, or document exact provenance/scope so review cannot be drowned in unrelated artifacts. Avoid deleting evidence needed for acceptance or retention without owner consent.

## What appears to be implemented correctly / no finding raised

- Positive full-string RU/EN/ES monthly-rent grammar, reconstructing bounded outbound text, and rejecting unknown conditions in the gate.
- Per-request DeepSeek adapter and transport wrapping budget reservation prior to I/O; no retry loop in pilot parser.
- Deterministic same-session/version/canonical-request identity for the pilot budget and fail-closed missing journal behavior.
- Read-only seed validation, isolated DB/Redis/maintenance in supplied Compose, and explicit SQL NULL preservation with regression test.
- Basic protection of site path and assets in the reviewed Nginx configuration, cookie path rewriting, and provider-only CONNECT destination (the test coverage/route scope still needs expansion).
- Typed result/intent comparison before accepting model output and reusing the existing owned-session/query proof chain.

These are observations about source and checked-in tests, **not** independent production certification.

## Acceptance criteria for Codex

1. Close PR411-01 and PR411-02: pilot bundle and proxy expose **only** explicitly approved AI functionality; nonpilot routes are denied. Confirm no changes to ordinary production route functionality.
2. Close PR411-03: real distinct clients have independent secure IP limits; spoofed headers cannot bypass limits.
3. Close PR411-04: incorrect Vite env/base/API/mock configurations fail the build. Verify deployed network paths and manifest provenance.
4. Close PR411-05: stale corpus blocks **before** provider budget reservation and business quota debit, without falsifying evidence freshness.
5. Add regression tests for secure cookies if auth exists, storage/origin scope, strict pilot input UX, reversed source selection, approval revocation and same-key replay; mock provider only.
6. Produce exact-head passing CI for all required workflows and record skipped gates and their predicates. Keep PR draft until acceptance.
7. Preserve all real DeepSeek usage, SQL state, erasure journal, signing keys, reserve accounting, current consent scope, and restricted source data. **No provider calls, no journal reset, no production migrations or deployment without separate explicit authorization.**
8. Before re-review, deliver an updated remediation matrix: finding ID → files touched → proof/test → pass/fail → known residual risk; compare new HEAD to reviewed `d2985d8` and include rollback procedure.

## Paste into Codex

> Review this repository at PR #411 and implement remediation based on `PR_411_CODE_REVIEW_FOR_CODEX.md`. First independently reproduce/confirm each P1 finding against current HEAD, separating actual bug from conditional exposure. Do not silently expand the AI pilot's trust/consent scope. Prioritize an AI-only backend proxy and frontend route boundary, secure per-client rate limiting behind Traefik+Nginx, build fail-closed environment enforcement, and stale-catalog pre-dispatch blocking. Add offline unit/integration/Playwright tests with a mock provider. Preserve all production resources and durable provider journal; never reset, refund, overwrite or make real paid provider calls. Keep changes surgical; don't alter ordinary site design/functionality. Run full existing CI/test/build/lint/migrations in isolated test infrastructure and report every failure, skip, risk and evidence path. Update README with timestamped counters, create a separate complete remediation report, and request review again. Do not merge or deploy automatically.
