# Remediation and production change plan

Everything below is a proposal. Source fixes and PR creation are authorized;
merging, live/test payment activation on production, host changes, credential
rotation, production restore and deployment need separate explicit approval.

## Review order

1. Dependency PR #345: review dated advisory scans and green compatibility CI.
2. Boundary-hardening PR: review connect-time HTTP policy, native decoder input,
   production test-payment gate, migration freeze and bounded log template.
   It includes the dependency commit until #345 merges; merge #345 first, then
   rebase/update and rerun required checks. No automatic merge is configured.
3. Treat runtime least-privilege DB access, browser egress isolation, SSH recovery,
   backup continuity, CSP, Docker socket and MFA as separate, rehearsed changes.
   Do not bundle unrelated host or product policy changes into this release.

## Proposed application rollout

Affected services: backend, mail/reconciliation worker, external importer,
frontend and Compose log configuration. No database DDL, migration file edit,
stateful image change, listing cleanup, gallery repair or financial-history
rewrite is proposed. Migration freeze was extended only after read-only
production-byte verification through 0063. Both static guard and frozen hashes
must remain valid after any rebase.

Before approval, confirm exact reviewed commit is current main after approved
merges; retain previous active release `8625775cafdd8ca58086a55294fc5f2309ccbe2b`.
Check live flag false and absent Stripe keys without printing values; leave
test-purchases flag false. Record dependency health, importer failure baseline,
disk space and current schema head. Produce fresh authenticated DB and MinIO
recovery points under the shared release lock and obtain restore evidence through
the separately approved drill process. Verify retained stateful image identities.

Only after approval, the operator uses the existing release mechanism:

```sh
/srv/112233.es/current/deploy/deploy-release.sh <approved-current-main-full-SHA>
```

That is documentation, not a command run by this audit. Do not bypass flock,
authenticated MinIO freshness, immutable worktree, image or readiness gates.
The script quiesces application writers and rebuilds/recreates application
services; expect an availability window. Exact downtime is unmeasured and must
not be advertised as zero. Template log changes require recreation; do not
separately recreate stateful services just to change logging during this patch.

Postchecks: public build SHA matches approved commit; authenticated synthetic
ownership flows; readiness; mail health; provider/source connectivity using
authorized non-mutating probes; preserved data-service identities; no unexpected
financial or entitlement changes; resource/5xx trends; known importer failure
is investigated rather than hidden. No live purchase/refund is a smoke check.

If rollback is required, with approval and compatible images/schema:

```sh
/srv/112233.es/current/deploy/rollback-release.sh 8625775cafdd8ca58086a55294fc5f2309ccbe2b
```

No downgrade is required or permitted. Rollback reintroduces old outbound/video
exposure and older dependency versions; record that residual risk and consider
temporary narrow upload/import containment if an active incident requires it.
Use provider console only through the verified operator recovery procedure if
SSH or readiness is unavailable. Do not restore a database over live volumes.

## Separate host/data changes

| Change | Required rehearsal and approval | Rollback |
|---|---|---|
| Runtime DB role | Create independent NOSUPERUSER/NOCREATEDB/NOCREATEROLE role; explicit CONNECT/USAGE/CRUD/sequence grants and reviewed default privileges. Test API, workers, PostGIS, migrations under separate owner and all deletion/payment paths in isolated DB. Install credentials through secret workflow. | Retain current owner credential protected; restore previous DATABASE_URL and approved application release if permission checks fail. Do not drop roles or revoke owner privileges during initial cutover. |
| SSH | Prove separate sudo administrator/key and provider console; test second session; review brute-force controls and forwarding needs before changing effective sshd settings. | Preserve current session/console; restore saved mode/owner-correct sshd snippet, validate with sshd -t and reload only. Never change routes/firewall concurrently. |
| Browser egress | Reproduce with synthetic DNS and internal decoy; isolate browser from data/host/metadata networks using separately reviewed network/proxy configuration. Test each approved source/provider path. | Restore reviewed prior browser configuration if availability regresses; retain source-specific containment if exploit is active. No blanket firewall flush. |
| Backup schedule/offsite | Rehearse bounded I/O, shared-lock contention, authenticated transfers, retention, key escrow and clean-host isolated restore; approve customer-data handling and destinations. | Disable only new schedule/transfer; retain all prior backups and evidence; never prune to recover from a failed setup. |
| CSP | Collect report-only violations; verify Maps, OAuth popups, media, payment redirects and all viewport/language flows before enforcement. | Restore previous reviewed header policy. No design changes. |
| Docker socket | Rehearse minimal allowed Docker discovery API and TLS renewal outside production; confirm routes and health. | Restore saved prior Traefik stack and routing; never replace Docker daemon/network rules during the same step. |
| MFA | Explicit admin enrollment, recovery codes, emergency operator path, sensitive-action challenge and lockout tests. | Use reviewed break-glass grant; do not disable account protections globally or print recovery codes. |

Owner-required decisions: approve proposed RPO/RTO, verified off-site destination
and console access; authorize sandbox Stripe testing; choose MFA adoption and
credential-rotation workflow. No additional host approval is requested until
the corresponding exact configuration and isolated evidence are reviewable.
