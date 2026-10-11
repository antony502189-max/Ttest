# Deploying to production (112233.es)

**Production:** `https://app.112233.es` on Contabo VPS **`169.58.147.65`** (expected hostname `vmi3640228`). GitHub Pages, Vercel and Netlify are **not** production targets. Source state in `main` is separate from the actually deployed server release.

## Only supported release path

1. Merge a reviewed PR into the protected `main` branch, after **all required CI checks** pass on that PR's latest SHA.
2. Check that no deployment/rollback/backup/restore operation is in progress. Never bypass the shared `flock` or force a concurrent release.
3. SSH into the **correct VPS**. Do **not** use the deprecated VPS `31.97.185.84`.
4. Fetch the actual `origin/main` on the server, prepare its immutable Git worktree and run the matching SHA through `deploy/deploy-release.sh`.
5. Confirm a final `status=success` in the release metadata, `current` pointing to that SHA, healthy containers and successful public-origin smoke test.

The safe script performs preflight validation of the environment (including mode 600), checksum/pinned-image checks, latest MinIO recovery-point verification, writer quiescence, an encrypted PostgreSQL backup, migration, Docker rebuild/start, backend readiness and a public health/build-fingerprint check. On failure in the controlled release flow, it attempts to restore the previous application release. **There may be a brief maintenance window.** The script does not purge listings or media.

## SSH deployment example (interactive Linux shell)

```bash
ssh root@169.58.147.65
```

Inside the VPS terminal only:

```bash
set -euo pipefail
root=/srv/112233.es
test "$(hostname)" = "vmi3640228"
test -r "$root/shared/production.env"
git -C "$root/repo" fetch origin --prune --tags
sha="$(git -C "$root/repo" rev-parse origin/main)"
echo "Selected main SHA: $sha"
test "$sha" != ""
release="$root/releases/$sha"
if [ ! -e "$release/.git" ]; then
  git -C "$root/repo" worktree add --detach "$release" "$sha"
fi
ROOT="$root" bash "$release/deploy/deploy-release.sh" "$sha"
ROOT="$root" bash "$release/deploy/smoke-production.sh"
readlink -f "$root/current"
```

The script itself performs strict validation; the example does **not** override its lock or manipulate production containers manually. Do not start this example if an earlier detached deployment is still running. On Windows, an SSH session can be started from PowerShell with the same host; paste the **Linux commands after connecting**, not as PowerShell syntax.

## Required acceptance

```bash
readlink -f /srv/112233.es/current
docker compose --env-file /srv/112233.es/shared/production.env \
  -f /srv/112233.es/current/docker-compose.production.yml ps
bash /srv/112233.es/current/deploy/smoke-production.sh
```

The smoke script verifies backend readiness, PostGIS, Redis, the **public HTTPS** site, the precise `build-info.json` commit fingerprint, legal pages and that production `/api/docs` and `/api/openapi.json` return 404. If the logs end with `status=success` but the public site serves an unexpected version, investigate Traefik/Nginx routing; do not repeat the deploy blindly.

**Note:** creating/updating documentation in `main` does not automatically deploy it to the VPS. A git merge SHA may be newer than the production release. Confirm both independently.

## Failure or lost SSH connection

- **No SSH output** is not proof the deploy stopped. A detached `deploy-release.sh` may still be running.
- Read-only inspect `pgrep -af deploy-release.sh`, `readlink -f /srv/112233.es/current`, `tail -n 80 /srv/112233.es/releases/<sha>.operator-*.log` (when present) and `cat /srv/112233.es/releases/<sha>.deploy-info`.
- If metadata is `in_progress` and a process is active, **wait; do not launch another**. If `status=failed`, confirm the rollback and read `<sha>.failed.log`.
- Do not remove lock files, delete old releases, run `docker compose down -v`, or clear DB/MinIO volumes to "fix" a deploy.
- For an authorized operator-controlled rollback, use `deploy/rollback-release.sh` according to [Production operations](production-operations.md). It rolls back application code but does not reverse incompatible/data-destructive migrations or earlier data maintenance.

See [Release checklist](release-checklist.md), [Production operations](production-operations.md), [Monitoring](production-monitoring.md) and [Troubleshooting](troubleshooting.md).
