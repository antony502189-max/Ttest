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
- dumps and checksums: `/srv/112233.es/backups` (mode `700`)

Start with `deploy/production.env.example`; copy it only on the VPS, generate independent strong values for every marked secret (including `BACKUP_ENCRYPTION_KEY`), URL-encode the password included in `DATABASE_URL`, and run `chmod 600 /srv/112233.es/shared/production.env`. Backups are AES-256-CBC/PBKDF2 encrypted on the VPS and checksummed. Never copy that file, dumps, Docker volumes, cookies, or logs containing secrets into Git.

`APP_DOMAIN` must resolve directly to `31.97.185.84` before deployment so Traefik can complete its HTTP ACME challenge. Set the Google Maps browser key only after restricting it to `https://112233.es/*` and `https://www.112233.es/*` and enabling only required Maps APIs. SMTP must be an actual configured provider; no Mailpit substitute is permitted in production.

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

The deploy script refuses non-main commits, validates compose, starts persistent dependencies, creates a pre-migration dump with checksum, migrates, builds/starts application services, and requires backend readiness. It records release metadata under `/srv/112233.es/releases/`. It never deletes volumes, releases, or backups.

Inspect services and logs:

```bash
docker compose --env-file /srv/112233.es/shared/production.env -f /srv/112233.es/current/docker-compose.production.yml ps
docker compose --env-file /srv/112233.es/shared/production.env -f /srv/112233.es/current/docker-compose.production.yml logs --tail=200 backend mail-worker external-listings-worker
docker compose -f /docker/traefik/docker-compose.yml ps
curl -I https://112233.es/
```

## Backup, restore and rollback

```bash
/srv/112233.es/current/deploy/backup-postgres.sh
/srv/112233.es/current/deploy/restore-verify.sh /srv/112233.es/backups/postgres-YYYYMMDD-HHMMSS.dump.enc
/srv/112233.es/current/deploy/rollback-release.sh
```

`restore-verify.sh` verifies the checksum, restores only into a timestamped temporary database, performs a minimal PostGIS/users query, and drops only that temporary database. `rollback-release.sh` switches only code/images after readiness succeeds; it does not run destructive database migrations and does not remove PostgreSQL, Redis, MinIO, Traefik, volumes, releases, or backups.

## Incidents and credential rotation

For a failed release, preserve logs, run the rollback script, then inspect the recorded deployment metadata and backup checksum. Do not run `docker system prune`, `docker volume prune`, `docker compose down -v`, or delete Traefik certificates.

To rotate JWT, database, or MinIO credentials: create a verified backup and restore test first; update only the VPS env file; apply the database/MinIO-side credential change using the vendor's supported procedure; then deploy a tested release and run the smoke check. Rotate one credential family at a time so a failure has a clear rollback path.

Before a controlled reboot, record `docker compose ps`, confirm there are no unknown workloads and all application services use `unless-stopped`, then reboot. Reconnect over SSH and repeat `smoke-production.sh`; do not reboot while an unknown workload or failed service remains.
