# Findings register

Severity is application risk, not an unadjusted scanner CVSS score. Confidence
refers to the observed defect, not proof of production exploitation. No active
compromise or P0 was established. FIXED BUT NOT DEPLOYED includes reviewable
source/config changes; runtime remediation is not claimed until deployment.

| ID | Priority | Finding | Confidence | Status |
|---|---|---|---|---|
| SEC-001 | P1 | Runtime database identity is a superuser | High | CONFIRMED |
| SEC-002 | P1 | Uploaded video can select network-capable native demuxers | High | FIXED BUT NOT DEPLOYED |
| SEC-003 | P1 | HTTP DNS validation was separate from the actual connection | High | FIXED BUT NOT DEPLOYED |
| SEC-004 | P2 | Vulnerable Python and build dependency pins | High | FIXED BUT NOT DEPLOYED |
| SEC-005 | P2 | Configured production Stripe test purchases could grant real services | High | FIXED BUT NOT DEPLOYED |
| SEC-006 | P2 | Public root password SSH without proven alternative recovery path | High | CONFIRMED |
| SEC-007 | P2 | Container json-file logs have no size/retention limit | High | FIXED BUT NOT DEPLOYED |
| SEC-008 | P2 | Backup cadence/offhost recovery are not established | High for observed local gap | CONFIRMED |
| SEC-009 | P2 | Public frontend lacks CSP and frame-ancestors | High | CONFIRMED |
| SEC-010 | P2 | Import worker is running with failed health | High | CONFIRMED |
| SEC-011 | P2 | Deployed payment migrations were outside the released freeze | High | FIXED BUT NOT DEPLOYED |
| SEC-012 | P2 | Traefik can access the privileged Docker API | High | CONFIRMED |
| SEC-013 | P1 | Chromium DNS/egress boundary may permit rebinding | Medium | NEEDS INVESTIGATION |
| SEC-014 | P2 | Administrator authentication lacks MFA/step-up | High | CONFIRMED |
| SEC-015 | P3 | Bandit treats a sentinel value as a hardcoded password | High | FALSE POSITIVE |
| SEC-016 | P2 | Historical generic-secret scanner matches require individual triage | Low as real credentials | NEEDS INVESTIGATION |

Counts: 16 registered items; 13 confirmed (including six patched), two needing
investigation, one false positive. P0=0, P1=4, P2=11, P3=1 (the false positive).
Excluding false positives: 15 risk/investigation items. Six source fixes await
merge; zero deployed fixes. Raw advisory/secret-match counts are separate.

## SEC-001 — Database privilege

Component/evidence: runtime database role metadata returned rolsuper,
rolcreatedb and rolcreaterole all true. Source: production Compose DATABASE_URL
and PostgreSQL POSTGRES_USER bootstrap; endpoint impact spans the whole API.
Precondition: app/worker compromise or arbitrary SQL capability. Boundary:
application → database administration. Impact: cluster-wide tampering, bypass
of role isolation and potential host-level effects available to a DB superuser.
CWE-250; ASVS v5.0.0 V8/V13 configuration families.

Fix: independent least-privilege runtime role, retained migration/backup owner,
tested grants and owner-approved credential cutover. Isolated reproduction:
connect as synthetic runtime role and query pg_roles; verify required CRUD and
that privileged role creation/filesystem functions fail. Production role was
only queried, not modified. Tests/rollback: see change plan; not yet rehearsed.
Regression/deployment risk: missing privileges can interrupt API/workers; high.

## SEC-002 — Native video network access

Files: `backend/app/services/video_processing.py`; POST `/api/v1/uploads/video`.
Precondition: authenticated uploader supplies bytes disguised as a video.
Boundary: uploaded content → FFprobe/FFmpeg → internal network. Impact:
server-side requests and decoder resource exposure. CWE-918/CWE-20;
ASVS v5.0.0-5.3.2 and 5.2.2.

Original invocation allowed format autodetection and unrestricted protocols.
Fix: file-only protocol plus a finite container-format allowlist on both probe
and transcode. Isolated evidence/test: `test_disguised_playlist_cannot_contact_a_local_service`
rejects HLS bytes and asserts zero loopback service requests, and real MP4,
MOV and WebM normalize successfully. No payload was sent to production.
Regression risk: uncommon playlist/non-self-contained video formats are rejected;
intended self-contained camera containers stay supported. Deployment risk: low,
normal application release; rollback restores old behavior and its exposure.

## SEC-003 — HTTP DNS rebinding

Files: `backend/app/core/public_http.py`, `backend/pyproject.toml`; importer
and other default HTTPX outbound callers. Precondition: attacker controls a
remote host/DNS reachable through accepted imported content. Boundary: public
content → data-network-connected worker. Impact: internal request side effects
can precede the old response-peer rejection. CWE-918/CWE-367;
ASVS v5.0.0-5.3.2, V4 outbound-service controls.

Fix: validate all connect-time DNS answers, connect to a public literal, retain
original Host/TLS SNI, bound DNS/connect time and reject proxy overrides. Tests
exercise the real HTTPX connection pool with synthetic socket I/O: private or
mixed answers open no socket; public connections keep original host/SNI.
Explicit ASGI/Mock transports remain supported for isolated callers.
Regression risk: internal HTTPX targets are intentionally denied; private API
between trusted services must use an explicitly reviewed transport. Version
coupling to pinned HTTPX/HTTPcore is documented. Browser path is SEC-013.
Deployment risk: medium; verify approved source discovery and Stripe/Google
reachability with owner-approved non-mutating checks after release.

## SEC-004 — Dependency advisories

Files: `backend/constraints.txt`, `package-lock.json`; components PyJWT,
urllib3 and build-time source-map-js. Evidence: pip-audit found 17 advisories
in two exact Python pins; npm found one high build-tool advisory. Application
exploitability depends on each advisory's prerequisites. In particular,
mixed-algorithm JWT key-confusion preconditions are absent. CWE-1104;
ASVS V13 dependency configuration. See DEPENDENCY-AUDIT.md.

Fix: PyJWT 2.15.0, urllib3 2.8.0, source-map-js 1.2.2. Both scans now report
zero. Compatibility: unit/integration/browser suites and malformed-token
regression. No uncontrolled resource-exhaustion proof was attempted. Risk:
minor dependency API/transport changes; existing pinned Linux graph and CI
validate compatibility. Roll back immutable application image only if required.

## SEC-005 — Production test entitlements / malformed signature

Files: Checkout service, payment API, settings and production env/Compose.
Endpoints: all `/payments/.../checkout`; signature parser at Stripe webhook.
Precondition: production later receives test credentials and a user completes a
test purchase. Boundary: test-money provider → real commercial inventory.
Impact: free paid services and reservation consumption. CWE-840;
ASVS V2 business-logic controls. This was not active in observed production.

Fix: explicit production-test acceptance flag, default false; live flag checked
at creation too. Existing reconciliation remains available. Tests cover every
environment/key/flag combination before persistence/provider work. Separately,
non-ASCII v1 signatures now return 400, rather than raising TypeError; rotating
valid digests continue to work. No production webhook was sent. Regression:
operators who intentionally use production test keys must explicitly accept the
business risk. Low runtime risk; currently no Stripe keys are installed.

## SEC-006 — Administrative SSH

Evidence: read-only sshd effective settings permit root and passwords;
fail2ban inactive. Component: host SSH, not a repository-managed sshd file.
Precondition: stolen/guessed password. Boundary: Internet → host administration.
CWE-308/CWE-250; ASVS V13 operations. Root access magnifies account compromise;
configuration alone does not establish a successful brute-force attack.
Fix/test: establish a second administrator and provider-console recovery first,
then approved key-only access and rate controls. Do not reproduce password
guessing. Console/access test and rollback are pending; lockout risk is high.

## SEC-007 — Log exhaustion

File: `docker-compose.production.yml`; evidence: runtime json-file options empty
for all inspected containers. Precondition: sustained normal/error/abuse logs.
Boundary: app logs → persistent host disk. Impact: outage or backup failure.
CWE-400; ASVS V16 logging. Fix: explicit 10 MiB/three-file rotation per app/data
service. Parsed-Compose regression verifies each definition. Production
recreation and independent Traefik retention need approval. Risk: reduced local
history; export/preserve incident evidence before retention changes.

## SEC-008 — Recovery continuity

Files reviewed: all `deploy/backup-*.sh`, freshness/prune/restore/rollback scripts.
Evidence: about 45-hour-old newest media archive, no app backup schedule found
in inspected cron/timers; no verified offsite recovery. The existing 72-hour
deployment gate still passes. Boundary: production → independent recovery.
Impact: unknown recovery point after host loss. CWE-693; ASVS V14 protection.
Fix: approved schedules, retention, offsite authenticated copies and recovery-key
escrow; verify isolated restore and measure proposed 24h RPO/4h RTO.
HMAC checks passed, restoration is not proven. No production restore was run.
Risk: backup CPU/I/O/capacity and customer-data handling require rehearsal.

## SEC-009 — Browser policy

File: `deploy/nginx.conf`; public HTML headers show no CSP. Precondition:
another script-injection/content inclusion weakness. Boundary: untrusted content
→ browser execution. CWE-693; ASVS v5.0.0-3.4.3/3.4.6/3.4.7. DENY framing exists,
but it does not satisfy CSP frame-ancestors. Fix: report-only policy with Maps,
Identity, media and Checkout compatibility evidence, then approved enforcement.
Do not deploy a guessed policy. Existing unit/browser tests do not prove CSP
compatibility. Medium regression risk; UI/provider flows may break.

## SEC-010 — Failed importer

Component: external-listings worker. Evidence: Docker unhealthy; persisted
health failed, current heartbeat, last success 14 October 08:06 UTC. Boundary:
external source availability → listing freshness. CWE-703; ASVS V16 monitoring.
Impact: stale/failed import work; no data corruption was established. Root cause
needs read-only source-specific diagnostic aggregation. Source allowlists and
health criteria must not be weakened just to turn health green. Isolated test:
simulate source/provider failure and heartbeat separately. No restart or source
change performed. Deployment risk depends on eventual root cause.

## SEC-011 — Released migration freeze

Files: `backend/alembic/released-migration-blobs.json`, compatibility guard and
its tests. Production applies 0063 while freeze ended at 0056. Boundary:
future code changes → applied immutable schema history. CWE-693; ASVS V13
configuration. Fix: compare production SHA-256 to exact Git bytes for 0057–0063,
then add their Git blob identities. Guard hash-verifies both historical sets
and applies future-DDL policy only to genuinely unreleased revisions. A new
test preserves rejection of constraint changes on already released tables.
Original SHA-256 baseline through 0032 and all migration files are unchanged.
Six guard tests and three governance tests pass. Source/CI change only; no
schema operation or production migration. Low deployment risk.

## SEC-012 — Docker API authority

Component: existing Traefik deployment outside app Compose. Evidence: root
container has `/var/run/docker.sock:ro`. Precondition: Traefik compromise or
misuse of its socket access. Boundary: edge container → host Docker daemon.
Impact: privileged host control; read-only mount does not limit API methods.
CWE-250; ASVS V13. Propose a minimal Docker socket proxy or isolated edge
discovery configuration with reviewed API/route needs. No write API call was
made. Rehearse route/certificate renewal and rollback on an isolated stack;
production availability risk is high.

## SEC-013 — Browser egress uncertainty

Files: `backend/app/core/browser_network.py`, importer Chromium launch paths.
Request routing validates DNS before Chromium's separate connection; the
worker also reaches the data network. CWE-918/CWE-367; ASVS V4/V5 boundaries.
Potential impact: internal requests from a compromised allowed source or
redirect/rebinding chain. No socket-level browser reproduction or exploitation
was executed; **not a confirmed production vulnerability**. The HTTPX fix does
not fix Chromium. Next: synthetic rebinding harness and an isolated browser
worker with explicit egress denial/proxy; preserve required source behavior.
Separate source/host plan and integration evidence required. Medium/high risk.

## SEC-014 — Privileged authentication

Files: auth/dependencies and AdminAccess; admin operations use one primary
credential/session without MFA or sensitive-action step-up. Precondition:
administrator credential/session compromise. Boundary: user identity → highly
privileged financial/moderation operations. CWE-308; ASVS V6 authentication.
Fix: explicit MFA enrollment/recovery/adoption, plus step-up for grant/refund
operations. Do not lock existing admins out by flipping a global flag. Test
synthetic enrollment, challenge replay, recovery and role-change revocation.
Not implemented; requires product and recovery approval before rollout.

## SEC-015 — Scanner false positive

Bandit B105 at `backend/app/services/mail.py:160` flags a sentinel string `None`,
not a hardcoded credential. The value is Python None, not a credential string.
Source inspection is the evidence. CWE-798 is not
applicable. No remediation or deployment; do not suppress the rule globally.
Other subprocess alerts are reviewed in SEC-002, not dismissed as proof of
safety merely because arguments are lists.

## SEC-016 — Historical secret candidates

Gitleaks 8.30.1 scanned 2,816 commits reachable from fetched main: 43 generic-key
matches in tests, mock fixtures, old CI, migration hash manifests and config
checks. Report was generated with 100% redaction; no matched secret value is
published. Current worktree and additional remote refs need separate coverage.
CWE-798/CWE-200; ASVS V13/V14. Candidate presence is confirmed; actual live
credential leakage is **not** confirmed. Each historical context needs triage;
do not call every match a leak or assume test-path placement proves safety.
If any value is real, classify it compromised and have the owner invalidate it.
Do not rewrite public history or rotate production secrets automatically.
