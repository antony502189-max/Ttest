# Incident response runbook

Owner/operator approval is required for containment that changes production.
An active P0 warrants immediate owner notification with minimal sanitized facts;
do not wait for a finished report. Record UTC detection time, affected release,
request IDs, resource symptoms and operator identity. Keep evidence in restricted
storage; hash snapshots, preserve access history and avoid customer/secret dumps.

| Incident | Evidence and proposed containment | Recovery / verification |
|---|---|---|
| Account or administrator compromise | Preserve auth/admin audit records; identify affected sessions and grant changes; propose session/grant revocation and temporary account restriction | Reset credentials through verified owner workflow; restore intended grants; prove old sessions fail and unrelated accounts work |
| Stripe key compromise | Preserve event/order IDs, delivery metadata and audit changes; propose disabling new checkout at edge/app and owner-driven key invalidation | Rotate through Stripe owner dashboard, redeploy approved server-only config, reconcile all uncertain orders; never blindly replay charges/refunds |
| Webhook secret compromise | Preserve raw event hashes in restricted evidence, signature failures and order outcomes; propose temporarily restricting webhook mutation and new purchases while maintaining provider delivery evidence | Rotate endpoint secret with supported overlap, verify signed synthetic events in approved sandbox; reconcile provider truth and financial inbox |
| Database breach | Record source/role/connection metadata and immutable release; propose isolating affected application path rather than deleting evidence | Rebuild trusted runtime and least-privilege credentials; assess data disclosure with responsible owner/legal advisers; reconcile records before reopening writes |
| MinIO exposure | Preserve bucket policy/ACL/object metadata; propose closing anonymous access or exposed routes after evaluating application impact | Owner-controlled storage credentials/policies; verify authorized media access and deleted/private object denial; do not erase objects |
| SSH/host compromise | Preserve login/audit/service and provider-console evidence; propose provider-side isolation only after a known console path is ready | Rebuild a clean host, invalidate exposed credentials, recover authenticated backups; verify keys, firewall and Docker exposure before reconnecting |
| Ransomware | Preserve evidence and stop propagation using owner-approved network controls; protect offline recovery copies | Rebuild from trusted images on clean infrastructure; validate offsite backups and key escrow; never assume a same-host archive is unaffected |
| Data loss/corruption | Preserve current volumes and operation timeline; stop affected writers only with approval; never overwrite originals with a guessed restore | Rehearse an isolated restore, verify DB/object linkage and data cutoff, reconcile post-backup transactions; approve cutover and record actual RPO/RTO |
| Active exploitation/availability incident | Capture bounded sanitized indicators and error/resource trends; propose narrow route/account containment before broad shutdown | Patch/review/test, controlled immutable deployment, observe readiness/error budgets and worker recovery; retain a tested rollback target |

Do not send passwords, bearer/refresh tokens, authorization headers, session
cookies, Stripe/webhook secrets, SMTP keys, storage keys, card data or raw
customer records in alerts. Avoid unbounded log collection on a full disk.

Before reopening service: validate backups and rollback, verify affected trust
boundaries with synthetic accounts, reconcile payments/entitlements, monitor
for recurrence and obtain owner acceptance. Post-incident review records the
root cause, affected period, data/financial impact, containment decisions,
evidence access, recovery measurements and assigned follow-up work.
Notification obligations and PCI scope require appropriate owner advisers;
this runbook does not establish legal deadlines or compliance.
