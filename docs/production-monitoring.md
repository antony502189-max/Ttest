# Production monitoring

This document covers the read-only post-acceptance checks for the VPS deployment. It complements `docs/production-operations.md`; it does not replace deploy, backup, restore, rollback, Sentry, provider-side alerts, or external uptime monitoring.

## One-command operational check

Run from the active release on the VPS:

```bash
bash /srv/112233.es/current/deploy/production-monitor-check.sh
```

The script is intentionally read-only. It does not restart containers, modify database rows, delete backups/releases, rotate credentials, or bypass source access controls.

It verifies:

- the `external-listings-worker` container is running and Docker reports its healthcheck as healthy;
- `external_worker_state` exists and its heartbeat is newer than `EXTERNAL_WORKER_STALE_AFTER_SECONDS`;
- worker database health is `healthy` or an actively heartbeating `running` cycle;
- the latest complete import cycle contains the configured source-run count and at least `EXTERNAL_IMPORT_MIN_HEALTHY_SOURCES` useful `SUCCESS` sources;
- a useful source has `discovery_complete=true` and positive `discovered_urls`, `fetched_details`, and `accepted_rooms` counters;
- filesystem usage for `/srv/112233.es` and `/var/lib/docker` remains below configurable warning/critical thresholds.

The default disk thresholds are 70% warning and 85% critical. They can be overridden for one invocation without editing production configuration:

```bash
DISK_WARNING_PERCENT=75 DISK_CRITICAL_PERCENT=90 \
  bash /srv/112233.es/current/deploy/production-monitor-check.sh
```

## Exit codes

| Code | Meaning |
| ---: | --- |
| `0` | healthy |
| `1` | critical failure |
| `2` | warning, currently disk-capacity related |
| `75` | maintenance/release operation in progress; the shared release lock is held |

A monitoring agent should treat `75` as maintenance rather than as a production outage. Deploy, rollback, backup and restore already share the same release lock.

## External import alerts

The worker already fails closed when fewer than `EXTERNAL_IMPORT_MIN_HEALTHY_SOURCES` sources complete the useful-import contract. The monitor check makes that state consumable by cron, a systemd timer, a VPS monitoring agent, or another alerting system without requiring an administrator web session.

Recommended alerts:

- immediate critical alert for exit `1`;
- warning alert for exit `2`;
- suppress outage paging for exit `75` while the release operation is bounded and expected;
- additionally inspect the administrator external-import run history when a source becomes `PARTIAL`, `BLOCKED`, or repeatedly `FAILED` even if the minimum healthy-source threshold remains satisfied.

Do not automate CAPTCHA solving, authenticated scraping, robots-policy bypasses, or access-control circumvention to clear a source alert. A blocked source should remain diagnostic evidence while the independent healthy-source threshold protects the catalog.

## Evidence to retain

For production incidents and periodic reviews, retain only non-secret evidence:

- exact active release SHA;
- monitor exit code and summary;
- worker/container health status;
- external import run IDs, source result states, discovery completeness and counters;
- backup/restore verification result;
- disk usage percentage.

Never attach `/srv/112233.es/shared/production.env`, database credentials, MinIO credentials, cookies, raw authentication headers, source challenge data, or secret-bearing logs to GitHub issues or CI artifacts.

## Still environment-specific

The repository cannot prove the following without the production provider accounts/environment, so they remain separate checks:

- Sentry receives a controlled test exception with the expected release/environment and no PII;
- Google Maps browser key is restricted to the production origin and only required APIs;
- Google OAuth production origins and redirect URIs work end-to-end;
- SMTP sender/domain verification and real inbox delivery are healthy;
- external alert delivery itself (for example, the VPS monitoring provider) is configured and tested.
