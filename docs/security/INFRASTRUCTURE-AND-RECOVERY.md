# Infrastructure, backups and recovery

See BASELINE.md for observed versions, release identity and resource state.
The backend and Python workers run as non-root app users, drop capabilities
and set no-new-privileges. Backend/mail root filesystems are read-only and
have bounded tmpfs/PID budgets. Importer root filesystem is writable to support
Chromium; containers have no memory caps. Frontend runs as UID 101, read-only.
Postgres/Redis/MinIO are not host-published. No application socket mount was
found; Traefik has Docker API access through a read-only filesystem mount.

Production container logs use json-file with empty options. The source template
now assigns 10 MiB × 3 files per service, including operations/init services.
This takes effect only after an approved container recreation; it does not
change the existing Docker daemon or Traefik configuration. Export retention
requirements before discarding old logs. Memory/CPU budgets need representative
workload measurements; arbitrary low caps could interrupt video/import work.

Database application identity has rolsuper, rolcreatedb and rolcreaterole true.
An internal-only port does not mitigate the resulting privilege after app/worker
compromise. New least-privilege runtime credentials must be separate from
migration/backup roles. PostgreSQL reports SSL off within the private bridge;
host-local trust and future cross-host links need separate decisions. Do not
revoke privileges before proving normal requests/workers and rollback.

Root SSH permits password login; fail2ban is inactive, maximum auth tries six,
TCP/X11 forwarding allowed. Existing local SSH keys were not accepted in the
read-only check; an independent administrator and verified Contabo console were
not established. Do not disable root/password SSH or modify UFW until these
recovery paths are demonstrated. A reboot-required marker is present; reboot
and patching are a separate availability change, not part of this audit.

## Backup evidence and limits

Production scripts use umask 077, mode-0600 environment checks, AES-256-CBC
with PBKDF2, separate independent HMAC-SHA256, temporary archive publication
and the shared release flock. Full database and object backups, restore drills,
freshness guard, retention/pruning and rollback scripts were reviewed.

Latest observed Postgres archive: 14 October 18:54 UTC, about 18 hours old.
Latest MinIO archive: 13 October 15:54 UTC, about 45 hours old. Both latest
archives' HMAC verification passed read-only. MinIO is within the existing
72-hour release gate; that gate is not a 24-hour RPO guarantee. Backup keys
meet minimum-length and independence checks. No restore was executed.

Restore-evidence filenames exist dated 6 October, but their content/success was
not independently validated. No application backup timer, root crontab or
backup/offsite command in inspected cron files was found. External scheduling,
offsite copies, retention enforcement and recovery-key escrow remain unknown.
Host-local encrypted backups plus keys on that same host do not establish
recovery after ransomware or total host loss.

Proposed, not approved: database RPO ≤24 hours, media RPO ≤24 hours, RTO ≤4
hours after clean-host availability. Rehearse with synthetic data first, then
obtain approval for an isolated encrypted production-data restore. No restored
environment may reach production SMTP/Stripe/OAuth/storage or customer traffic.
Measure elapsed restoration and reconcile database-to-object references.

## Operations and monitoring

Current external worker has fresh heartbeat but failed health; last success is
over a day old. A follow-up aggregate import query could not be completed
because its assumed table shape differed (recorded as unverified); no raw error
or customer data was exported. Do not mask this condition by changing health
criteria or restarting production without approval. Sentry is unconfigured;
metrics and structured logs exist, but external scraping, alert routing and
historical SLO/error baselines were not established.

Proposed alerts: worker failed/stale >10 minutes; readiness failure >2 minutes;
5xx >2% with ≥100 requests/5 minutes; paid review queue older than 15 minutes;
webhook validation-failure spikes; backup age >24 hours warning / 48 hours
critical; disk >80% warning / 90% critical. Tune to measured traffic, deduplicate
and page only actionable sustained conditions. Never attach credentials,
request Authorization/cookies, OTPs, payment details or customer records.

TLS redirect, HSTS, no-referrer, nosniff, framing denial and COOP were observed.
CSP is absent. Certificate expiry/renewal failure history, edge dashboard auth,
DNS/Cloudflare controls and network-provider DDoS protection remain unverified.
Application request limits do not mitigate volumetric upstream saturation.
