# PR 394 review resolution

The supplied review examined9549ad9f. This revision fixes its eight findings
while retaining disabled public runtime and all392/393 review corrections.
No production policy defaults, real provider, application database, migration,
automatic cleanup worker, notification or deployment are introduced.

| Finding | Correction and evidence |
| --- | --- |
| F-01 trusted IP | Required AIHTTPPolicy declares immutable trusted proxy networks. Only a peer inside that explicit allowlist may supply the existing sanitized client_ip headers. Direct untrusted peers cannot rotate forwarded addresses. Both HTTP and guest-issue keys share this policy; subject mint keys are HMACed too. Contract tests use two users behind one trusted proxy and forged headers outside it. Universal IPv4/IPv6 trust is rejected. |
| F-02 CORS | Exact allow_headers now includes X-AI-Request. Allowed/denied OPTIONS plus subsequent POST tests exercise the real application middleware. The real Chromium loopback test also sends a cross-origin JSON POST with the mandatory header; a readable403 proves the browser preflight passed and the endpoint enforced the guest deployment boundary. No wildcard origin/header is added. |
| F-03 private paths | Application request, error and validation paths plus metrics use one fixed private category even for unknown/unvalidated paths. Private unhandled errors omit traceback/text. Uvicorn access events containing private paths are dropped; the dedicated nginx AI location disables raw access/error logging and retains proxy sanitation/abuse settings. Sentinel tests cover malformed session/result/unmatched paths and server access logger. |
| F-04 price periods | VerifiedCardResult now carries budget_prices for each returned card with a hard budget: actual matched_amount/matched_period, native display_amount/display_period, currency and current_source_proof confirmation. Values are read in the same repeatable-read snapshot, only for already verified IDs. No conversion or replacement of native card/TOP prices. Full PostGIS regressions cover weekly budget with long rental and monthly budget with holiday rental, asserting encoded response amounts/periods. The dependent UI renders the confirmed budget amount beside the native card. |
| F-05 cookie deployment | Guest flow explicitly supports same-origin UI/API reverse proxy only; foreign Origin or Sec-Fetch-Site is rejected before mint/read. Bearer clients retain allowlisted cross-origin CORS. Secure/HttpOnly/SameSiteStrict are preserved. Real loopback Chromium checks same-origin creation/read identity, inaccessible document.cookie and cross-site rejection without a replacement cookie. |
| F-06 session growth | Required HTTP policy supplies active-session bound. Create/reset call a separate injected per-subject issuance gate. PostgreSQL serializes creation per subject and checks unexpired/open count atomically; mint/reset never spend/reset LLM quota.110concurrent creates test the bound. Explicit bounded cleanup_unused requires an aware caller-chosen past retention cutoff, skips locked rows, and preserves every referenced operation/result/session. Synthetic tests prove batch limits/audit preservation. There is no worker, chosen retention period or application-data cleanup. |
| F-07 complete deadline | Required finite positive request_seconds covers HTTP gate, streaming body, ownership/dependencies, parser/query/finalize and encoding; late synchronous completion is rejected. Deadline propagates into cancellation cleanup so an exhausted HTTP budget cannot start an unbounded release. Pre-success cancellation leaves a fenced reservation for existing recovery; callback writes roll back. After possible commit, boundary returns504 requiring exact-operation replay and never speculatively releases. Real PG tests exercise parser/query timeout, cancellation inside uncommitted callback and lost acknowledgement after committed debit; replay never repeats inference/debit. |
| F-08 errors and capabilities | Quota exhaustion carries Retry-After computed from PG's Madrid reset/clock; HTTP attempt limiter exposes its reliable retry delay. Active-session limit reports earliest expiry. No arbitrary retry delay is invented when unavailable. Capabilities explicitly advertise configuration, not dependency health; a broken-gate test proves the distinction and no health probe calls providers/DB. Existing readiness/activation approval stays separate. |

## Important boundaries

The HTTP deadline is a cooperative async cancellation boundary, not a process
sandbox for malicious blocking Python. Slow synchronous work cannot be preempted;
its late result is rejected. Production SQL/driver/ingress timeouts and bounded
provider adapters must be reviewed together with the explicit HTTP/lease budgets.
504 can mean a committed result whose acknowledgement was lost: only retrying
the same operation key/body/version resolves it. An unfinished reservation stays
unavailable until fenced recovery, never becoming permission to infer again.

The gate contract is required and fail closed; this PR supplies no permissive
in-memory limiter or production issuance budget. A runtime factory must provide
the distributed per-IP/issue/per-subject gate policies, explicit proxy networks,
HTTP deadline and maximum active sessions before activation. Capabilities do not
promise health or an SLA. Source snapshot equality is not coverage/freshness.

The browser tests use loopback sites with trusted synthetic runtime and no
database/provider. They are not verification of the owner's live nginx/Traefik
deployment. nginx syntax and infrastructure tests run in isolated CI; actual
ingress trust/ASGI forwarding must be verified before activation without
silently enabling a public AI runtime. Upstream infrastructure logging remains
an operator privacy gate. No production p95 claim follows from correctness CI.

Local final and exact-head CI evidence is recorded in the PR description after
the corrected commit is pushed. Previous-head green checks are historical.
