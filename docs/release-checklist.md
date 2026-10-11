# Production release checklist

Use this checklist for any change affecting the running site. **A merged PR, a green CI badge and a production deployment are three distinct events.**

## Before merge

- [ ] PR scope is reviewed; no unintended feature or pricing changes (`Vivienda` and `Turismo` preserved).
- [ ] Tests cover changed user flows, backend contracts, safety and any new migrations.
- [ ] Current PR HEAD passes `frontend-static`, `backend-production`, `safeguards`, `snapshot`, `full-audit`, mobile E2E shards and required `validate`/publication checks. Follow the actual branch rules, not this list alone.
- [ ] Data models and migrations remain backward-compatible with the previous release; applied migration history untouched.
- [ ] No secrets, production dumps, personal data or unapproved media entered code/tests/docs.
- [ ] Region/map changes have spatial and visual tests; publication/media changes have upload/gallery tests.
- [ ] README and affected runbooks updated; operational changes identify rollback and recovery impact.

## Before deploying

- [ ] Record the **exact 40-character `origin/main` SHA** and confirm PR merged.
- [ ] Confirm VPS hostname `vmi3640228`, IP `169.58.147.65`, `APP_DOMAIN=app.112233.es`; do not deploy to an old server.
- [ ] Confirm target has no ongoing deploy/rollback/backup/restore; shared `flock` free.
- [ ] Confirm `/srv/112233.es/current` is present and corresponds to a known clean worktree.
- [ ] Confirm `production.env` permissions are 600 and secrets are not printed/logged.
- [ ] Check disk/inodes, container health, PostgreSQL/MinIO status, recent verified encrypted backups and restore-drill history.
- [ ] If new data-service images are involved, **stop** ordinary deploy and use separate reviewed data-service migration procedure.
- [ ] Arrange a maintenance window if external worker or application writes must stop; communicate downtime appropriately.

## Deploy

Run only the controlled `deploy/deploy-release.sh <origin-main-sha>` from a correctly prepared immutable release worktree. The script owns writer quiescence, DB backup, MinIO freshness gate, Alembic, Docker compose startup, smoke check and automatic app rollback. Do not manually retry migrations while this process is running. Preserve operator log and metadata for incident response.

## Post-deploy acceptance

- [ ] `readlink -f /srv/112233.es/current` ends in the expected full SHA.
- [ ] `/srv/112233.es/releases/<sha>.deploy-info` ends with `status=success`.
- [ ] `deploy/smoke-production.sh` passes including public domain, build fingerprint, DB, Redis and private Swagger behavior.
- [ ] Frontend/backend/workers are healthy; logs show no unexpected migration/import/media errors.
- [ ] Version at `https://app.112233.es/build-info.json` matches expected SHA.
- [ ] Manually inspect the changed feature on a real/mobile browser after hard reload where appropriate. For Spain region selector: 17 options, Barcelona → Cataluña, counter → same filtered results, correct header and `comunidad` persistence. For map: 70 km recall after fresh revisit, no ad-opening requirement.
- [ ] Confirm no unauthorized catalog maintenance occurred (`data_maintenance=skipped`).
- [ ] Compare worker/importer status against pre-release baseline, not CI fixtures.

## If anything fails

1. Preserve redacted log and release metadata; do not declare success early.
2. If the script reports rollback, confirm `current`, services and public smoke after the rollback.
3. If no active process exists but metadata is ambiguous, investigate before restarting. Do not double-run.
4. Use `rollback-release.sh` only under the documented change plan; it cannot undo destructive business data changes.
5. Keep database, media, backups and Traefik volumes intact.

After a stable deploy, add the exact SHA, date, operator-approved checks and any deviations to your private release tracking system (no secrets in public documentation). [Deployment](deployment.md) · [Production operations](production-operations.md).
