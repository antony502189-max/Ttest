# Production operations

Production runs entirely on the VPS. Existing Traefik remains the sole public listener for ports 80/443; it discovers the `frontend` container through Docker labels. PostgreSQL/PostGIS, Redis, MinIO and FastAPI have no published host ports.

```text
Internet -> Traefik (80 redirects to 443) -> frontend (nginx)
                                           -> /api/v1 FastAPI
FastAPI -> PostgreSQL/PostGIS | Redis | private MinIO | SMTP
workers -> PostgreSQL/PostGIS | Redis | private MinIO | SMTP
```

## Server layout and secrets

- checkout cache: `/srv/112233.es/repo`
- immutable releases: `/srv/112233.es/releases/<commit-sha>`
- active release symlink: `/srv/112233.es/current`
- compose file: `/srv/112233.es/current/docker-compose.production.yml`
- secret env file: `/srv/112233.es/shared/production.env` (mode `600`)
- encrypted backup sets and authentication sidecars: `/srv/112233.es/backups` (mode `700`)
- release-operation lock: `/srv/112233.es/shared/release.lock` (mode `600`)

Start with `deploy/production.env.example`; copy it only on the VPS, generate independent strong values for every marked secret (including independent `BACKUP_ENCRYPTION_KEY` and `BACKUP_AUTHENTICATION_KEY` values), URL-encode the password included in `DATABASE_URL`, and run `chmod 600 /srv/112233.es/shared/production.env`. PostgreSQL dumps and MinIO object archives are AES-256-CBC/PBKDF2 encrypted on the VPS and authenticated with HMAC-SHA256. Never copy that file, dumps, Docker volumes, cookies, or logs containing secrets into Git.

`APP_DOMAIN` must be `app.112233.es` and resolve directly to `31.97.185.84` before deployment so Traefik can complete its HTTP ACME challenge. Set the Google Maps browser key only after restricting it to `https://app.112233.es/*` and enabling only required Maps APIs. SMTP must be an actual configured provider; no Mailpit substitute is permitted in production.

Bootstrap the server once after DNS and SMTP are ready. This creates directories and a source checkout only; it does not start application containers:

```bash
install -d -m 700 /srv/112233.es/shared /srv/112233.es/backups /srv/112233.es/releases
git clone https://github.com/antony502189-max/Ttest.git /srv/112233.es/repo
cp /srv/112233.es/repo/deploy/production.env.example /srv/112233.es/shared/production.env
chmod 600 /srv/112233.es/shared/production.env
# edit the VPS-only env file with the real, independently generated credentials
git -C /srv/112233.es/repo fetch origin --tags
git -C /srv/112233.es/repo worktree add --detach /srv/112233.es/releases/<sha> <sha>
```

## Deploy and verify

After a green PR is merged, fetch local main, use its full SHA, and run on the VPS:

```bash
/srv/112233.es/releases/<sha>/deploy/deploy-release.sh <40-character-main-sha>
/srv/112233.es/current/deploy/smoke-production.sh
```

The deploy script accepts only the exact current `origin/main` SHA. For an existing installation it first verifies that the digest-pinned PostgreSQL, Redis and MinIO images are identical to the active release. A stateful image change is refused before writers stop and requires a separate controlled data-service migration and recovery plan. The normal release then enters a bounded maintenance window by stopping all write-producing application services, starts PostgreSQL/MinIO from the **previous** release definition, creates encrypted authenticated backups, and only then starts dependencies from the new release and applies migrations. Existing persistent volumes without a known `current` release fail closed. The script builds/starts application services and requires backend readiness. It records the previous/new SHA, backup runtime SHA, migration revisions and image IDs under `/srv/112233.es/releases/`; deployment metadata and failure logs are created under a restrictive process umask. It never deletes volumes, releases or backups; older code must be selected through `rollback-release.sh`, not the normal deploy path.

Deploy, rollback, scheduled/direct backup, and restore-verification scripts share one non-blocking `flock`. A concurrent operation exits with status `75` before touching release state. Do not bypass that lock or delete its file while an operation is running. The migration baseline file freezes the SHA256 of every deployed Alembic revision through `0032_media_reference_guard`. CI rejects edits to that history and requires later upgrades to remain expand-only: no removal or rename, type/default replacement, nullability tightening, new constraints/unique indexes, or irreversible row deletion while the previous application release remains a rollback target.

Inspect services and logs:

```bash
docker compose --env-file /srv/112233.es/shared/production.env -f /srv/112233.es/current/docker-compose.production.yml ps
docker compose --env-file /srv/112233.es/shared/production.env -f /srv/112233.es/current/docker-compose.production.yml logs --tail=200 backend mail-worker external-listings-worker
docker compose -f /docker/traefik/docker-compose.yml ps
curl -I https://app.112233.es/
```

## External listing sources

The `external-listings-worker` is a persistent production service. It uses the configured public adapters, Redis's distributed lock, bounded per-source concurrency, request timeouts and exponential retries. It starts after a VPS reboot through `restart: unless-stopped`; its healthcheck fails if the worker has no recent heartbeat or reports a failed all-source cycle.

Use the admin API's `GET /api/v1/admin/external-import/worker` and `GET /api/v1/admin/external-import/runs` endpoints (with an administrator session) to see the last successful run, source counters, partial runs, blocks and diagnostics. The worker logs only source/run metadata and counters; do not place credentials, cookies or challenge-solving data in a source configuration.

To add a source, first confirm that anonymous public access and the source's terms/robots policy permit the adapter. Implement an `ExternalListingSource` subclass in `backend/app/external_sources.py` with independent discovery URLs, URL matching, parsing, normalization and confirmed-removal handling; register its lower-case name both in `configured_sources()` and `SUPPORTED_EXTERNAL_IMPORT_SOURCES`. Add parser fixtures plus lifecycle integration coverage for create, idempotent re-import, update and unavailable-source behavior. After review, make the production default source set reflect the approved sources (or add a documented VPS-only `EXTERNAL_IMPORT_SOURCES` override where an environment-specific exception is required), then deploy a merged `main` SHA. Do not bypass CAPTCHA, authentication, robots policy or access controls. A blocked adapter is recorded with diagnostics and does not stop other configured adapters or trigger mass deactivation.

## Backup, restore and rollback

```bash
/srv/112233.es/current/deploy/backup-production.sh
/srv/112233.es/current/deploy/disaster-recovery-cycle.sh
/srv/112233.es/current/deploy/offsite-restore-drill.sh
/srv/112233.es/current/deploy/restore-verify.sh /srv/112233.es/backups/postgres-YYYYMMDD-HHMMSS.dump.enc
/srv/112233.es/current/deploy/restore-minio-verify.sh /srv/112233.es/backups/minio-YYYYMMDD-HHMMSS.tar.enc
/srv/112233.es/current/deploy/rollback-release.sh
# For a legacy installation without deploy metadata only:
/srv/112233.es/current/deploy/rollback-release.sh <40-character-target-sha>
```

`backup-production.sh` publishes one authenticated backup-set manifest only
after both local encrypted artifacts exist and pass HMAC verification.
`disaster-recovery-cycle.sh` uploads that exact set to the independent
S3-compatible destination through the egress-only `offsite-tools` service. It
then downloads and re-authenticates every uploaded object before recording
success. The bucket also contains one atomically replaced
`latest-backup-set.tar` locator: it bundles the authenticated set manifest and
sidecar, allowing a replacement VPS to find the latest complete set without any
file from the lost host.

Off-site recovery is not active merely because these files exist in Git. Store
the encryption/authentication keys independently of the VPS, configure an
independent bucket and provider-side versioning/retention or object lock, set an
external alert destination, and explicitly run
`deploy/install-production-ops.sh` as root. The ordinary deploy path never
installs or enables these timers. Do not claim recovery readiness until the
first real replication and `offsite-restore-drill.sh` run both succeed.

`restore-verify.sh` verifies the checksum, restores only into a timestamped temporary database, performs a minimal PostGIS/users query, and drops only that temporary database. `restore-minio-verify.sh` restores only into a timestamped temporary bucket, lists the restored objects, and deletes only that temporary bucket. Without arguments, `rollback-release.sh` uses the exact `old_sha` recorded by the current deployment instead of guessing from directory timestamps; the explicit SHA form is only for legacy recovery when metadata is absent. Rollback refuses targets whose PostgreSQL, Redis or MinIO image digests differ from the current release. For a compatible target it restores dependency definitions and application code only after bounded readiness succeeds. If the target fails readiness, the script restores current dependencies and application containers and keeps the `current` symlink unchanged. It does not run destructive database migrations and does not remove PostgreSQL, Redis, MinIO, Traefik, volumes, releases, or backups.

## Incidents and credential rotation

For a failed release, preserve logs, run the rollback script, then inspect the recorded deployment metadata and backup checksum. Do not run `docker system prune`, `docker volume prune`, `docker compose down -v`, or delete Traefik certificates.

To rotate JWT, database, or MinIO credentials: create a verified backup and restore test first; update only the VPS env file; apply the database/MinIO-side credential change using the vendor's supported procedure; then deploy a tested release and run the smoke check. Rotate one credential family at a time so a failure has a clear rollback path.

Before a controlled reboot, record `docker compose ps`, confirm there are no unknown workloads and all application services use `unless-stopped`, then reboot. Reconnect over SSH and repeat `smoke-production.sh`; do not reboot while an unknown workload or failed service remains.
