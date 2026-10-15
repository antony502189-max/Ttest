# Security readiness report — 15 October 2026

**Verdict: REQUIRES REMEDIATION. Not ready to enable production payments.**

This is a substantive source/read-only infrastructure audit with tested patches,
not a guarantee of complete security or a complete ASVS Level 2 attestation.
Internal maturity assessment: **partial application controls; unresolved
privileged infrastructure and recovery boundaries**. This is a qualitative
internal heuristic, not a score representing likelihood of compromise.

## Findings and delivered changes

16 registered items: P0=0, P1=4, P2=11, P3=1. Thirteen are confirmed,
two require investigation, one is a scanner false positive. Six confirmed
findings have source/config fixes and are awaiting merge; zero are deployed.
Counts exclude raw 17 dependency advisories and 43 secret candidates from the
confirmed-vulnerability total. See FINDINGS-REGISTER.md for preconditions,
evidence, CWE/ASVS references, regression/deployment risks and exact statuses.

P1: production application DB role is a superuser; video decoder and HTTP
connection boundaries are patched but not deployed; Chromium egress/rebinding
remains an unverified high-impact boundary. No active P0 was established.

Patched: vulnerable package pins, HTTP connect-time IP pinning, native video
protocol/container restrictions, default production test-payment denial,
malformed webhook signatures, bounded container log templates, and the applied
migration freeze/compatibility gate. No schema migration or UI source change.

## Payment readiness

Production runs reviewed release `8625775cafdd8ca58086a55294fc5f2309ccbe2b` and
schema 0063. Stripe key and webhook secret are absent, live flag false and
payment orders empty. Synthetic tests support amount/currency/environment
binding, signed webhooks, duplicate/late events, capacity/idempotency,
refund/dispute handling and retained entitlements. No live or provider sandbox
financial test was executed. Actual Stripe account/webhook setup, financial
fault injection and approved activation still require verification. Keep
production payments disabled. Hosted Checkout does not establish PCI approval.

## Infrastructure and recovery readiness

Public listeners are limited to SSH/HTTP/HTTPS; data services and backend have
no host-published ports. Runtime API/mail/data health is good, importer health
failed. Root password SSH, superuser DB access, edge Docker API authority,
unbounded current logs, missing CSP and unproven backup automation/offhost
recovery remain risks. Backup encryption/authentication controls are present;
latest archive HMACs pass, but restoration and actual RPO/RTO remain unproven.
Do not reboot, change firewall/SSH, rotate credentials or restore data as an
automatic consequence of this report.

## Validation and review

Updated constrained Linux suite: 753 unit tests passed (three conditional skips)
and 258 real PostgreSQL/PostGIS/Redis plus one MinIO integration test passed. Targeted native
video/HTTP regressions and 30 Chromium payment scenarios passed. Frontend
static/build/bundle/dependency checks and backend lint/type checks passed.
Dependency scans report zero known findings after the narrow pin updates.
Migration guard/governance checks pass without modifying applied migrations.
See TEST-EVIDENCE.md for tool versions, repaired environment failures and limits.

Repository: https://github.com/antony502189-max/Ttest.
Dependency branch: `codex/security-dependency-pins-2026-10-15`, commit
`ab1867a2`, [PR #345](https://github.com/antony502189-max/Ttest/pull/345).
Boundary branch: `codex/security-boundaries-2026-10-15`, implementation commit
`573e0c6f815fd5906c7c12d3ccfdbe803248300e`,
[PR #346](https://github.com/antony502189-max/Ttest/pull/346). Subsequent validation
and documentation revisions may follow; the final PR head and its live checks
are the authoritative review target. No merge/deploy approval
has been granted. CI success is not evidence of production deployment.

Recommended next actions: review/merge only with explicit owner approval and
green final-head CI; rehearse least-privilege DB and browser isolation; establish
console/admin recovery and offhost restore; investigate unhealthy importer and
secret candidates; stage CSP/MFA and password-blocklist adoption separately.
Then submit the immutable release/backup/rollback plan for separate deployment
approval. Detailed operational steps are in
REMEDIATION-AND-PRODUCTION-CHANGE-PLAN.md; incident response is in
INCIDENT-RESPONSE.md.

## Report map and limits

BASELINE.md and ASSET-INVENTORY.md establish scope and assets; API-INVENTORY.md
lists 125 HTTP operations; THREAT-MODEL.md maps STRIDE boundaries;
OWASP-ASVS-MATRIX.csv covers all official requirement identifiers and identifies
unverified clauses; APPLICATION-SECURITY.md covers identity, authorization,
API/frontend, media and imports; PAYMENT-SECURITY-AUDIT.md covers finances;
INFRASTRUCTURE-AND-RECOVERY.md covers host/Docker/TLS/database/backup/monitoring;
DEPENDENCY-AUDIT.md covers supply chain. Suggested numbered reports were
consolidated to keep evidence and decisions together.

Residual limitations include no full per-endpoint role-negative matrix, no
complete requirement-level ASVS sign-off, unverified Chromium network behavior,
actual restore/host-loss recovery, provider consoles/edge controls, current
image OS CVEs, secret-history triage and comprehensive telemetry redaction.
No claim of complete security, payment certification or absence of compromise
is made.
