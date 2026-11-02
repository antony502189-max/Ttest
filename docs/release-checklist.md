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

- [ ] Record the **exact 40-character `origin/main` SHA** and confirm PR merged; a merge alone is not a deployment.
- [ ] Confirm the latest **push** runs on that exact SHA passed Full audit, Security dependency and static audit, Capacity smoke safeguards, AI Search combined facts quota sessions, and AI Search private frontend. The release verifier rejects missing, pending, skipped or failed runs; green PR checks alone are insufficient. See [post-merge remediation](post-merge-remediation.md).
- [ ] Confirm VPS hostname `vmi3640228`, IP `169.58.147.65`, `APP_DOMAIN=app.112233.es`; do not deploy to an old server.
- [ ] Confirm target has no ongoing deploy/rollback/backup/restore; shared `flock` free.
- [ ] Confirm `/srv/112233.es/current` is present and corresponds to a known clean worktree.
- [ ] Confirm `production.env` permissions are 600 and secrets are not printed/logged.
- [ ] Check disk/inodes, container health, PostgreSQL/MinIO status, recent verified encrypted backups and restore-drill history.
- [ ] If new data-service images are involved, **stop** ordinary deploy and use separate reviewed data-service migration procedure.
- [ ] Arrange a maintenance window if external worker or application writes must stop; communicate downtime appropriately.

## Deploy — normal GitHub Actions route

- [ ] Open [Production deployment (manual approval)](https://github.com/antony502189-max/Ttest/actions/workflows/manual-production-deploy.yml); select `main`, tick explicit production confirmation and choose **Run workflow**.
- [ ] **Confirm exact main commit and passing PR CI** completes successfully. The selected SHA is the **latest** `main` SHA and has approved merged-PR check evidence.
- [ ] **Verify post-merge checks on exact main SHA** succeeds before the deployment job. Optional Pages publication is independent and requires explicit `PAGES_PREVIEW_ENABLED=true`; preview settings never authorize a VPS deployment.
- [ ] If the deployment is waiting for review, use **Review deployments → Approve and deploy** on `production`. Self-approval needs **Prevent self-review disabled** and the operator listed among Required reviewers. Alternatively use a second authorized approver.
- [ ] **Do not modify `main` while the release is running** and do not run another deploy or backup concurrently. The VPS verifies that approved SHA still equals `origin/main`.
- [ ] **Deploy manually approved release to VPS** completes green. The restricted VPS runner invokes the established release engine: MinIO freshness gate, PostgreSQL backup, Alembic, Docker startup, smoke test and safe application rollback where supported. Preserve logs and metadata for incident response; don't retry migrations manually.

Only a separately authorized operator should use `deploy/deploy-release.sh <exact-origin-main-sha>` as a **manual SSH fallback**, from a prepared immutable release worktree. See [GitHub Actions quickstart](deploy-quickstart-ru.md) and [deployment runbook](deployment.md).

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

After a stable deploy, add the exact SHA, date, operator-approved checks and any deviations to your private release tracking system (no secrets in public documentation). [Actions quickstart](deploy-quickstart-ru.md) · [Deployment](deployment.md) · [Production operations](production-operations.md).
