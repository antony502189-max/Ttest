# Deploying to production (112233.es)

**Production:** `https://app.112233.es` on Contabo VPS **`169.58.147.65`** (expected hostname `vmi3640228`). GitHub Pages, Vercel and Netlify are **not** production targets. Source state in `main` is separate from the actually deployed server release.

## Recommended: deploy from GitHub Actions

**Normal release does not require a developer to SSH into production.** GitHub's one-click release is **manually initiated**, then automatically executed by the VPS deployment engine after CI and the required environment confirmation. **There is no production deployment on push, merge or PR close.**

### Operator procedure

1. Work in a feature branch. Open a PR, validate the changed functionality, pass required CI checks, and merge it into **`main`**.
2. Verify no other deployment, rollback or backup is still executing. **Do not change `main` while a deployment is running**: the target SHA must continue matching `origin/main`.
3. Open [Actions → Production deployment (manual approval)](https://github.com/antony502189-max/Ttest/actions/workflows/manual-production-deploy.yml). Click **Run workflow**, select **main**, enable the explicit production confirmation checkbox, then click **Run workflow** again.
4. Wait for **Confirm exact main commit and passing PR CI** to turn green. This job refuses unconfirmed requests, non-`main` commits, a stale SHA, merges without PR evidence and missing required CI. **Do not approve** if this validation fails.
5. If the workflow is **Waiting for review**, open **Review deployments**, select `production`, and click **Approve and deploy**. To let the same operator approve their own run, the `production` environment must have that user as a required reviewer and **Prevent self-review disabled**. If that option is enabled, an independently designated reviewer must approve instead.
6. Wait for **Deploy manually approved release to VPS** to finish. Do not cancel it casually, run another release, or push new commits to `main` while it is in progress.
7. Verify green jobs, production `current` SHA, `status=success` metadata, public [`build-info.json`](https://app.112233.es/build-info.json), and the changed feature in an actual browser.

See **[Russian quickstart for a new developer](deploy-quickstart-ru.md)** and [CI/CD environment setup and security](manual-production-cicd.md).

### GitHub Environment and access controls

The workflow uses **exactly** the GitHub Environment named `production`, restricted to branch `main`. Its **Required reviewers** setting adds a manual approval gate; the operator can self-approve only when **Prevent self-review** is unchecked. If required reviewers are disabled, the `deploy` job runs after passing CI without a second approval click, but still requires the manual workflow dispatch checkbox. These settings are configured in the GitHub UI, not in the YAML.

The SSH integration uses two **Environment secrets**: `PRODUCTION_SSH_PRIVATE_KEY` (dedicated GitHub Actions → VPS key) and `PRODUCTION_SSH_KNOWN_HOSTS` (pinned VPS host identity). Do not print, publish or send the private key. The VPS authorization uses a **forced command** and `restrict`; GitHub Actions cannot use that key for a normal administrative shell.

### What the release does on the VPS

After approval the workflow uses a restricted SSH connection to `/usr/local/sbin/112233-manual-production-deploy` on `vmi3640228`. The runner starts a systemd-managed release for the exact reviewed SHA, preserves progress across SSH disconnections, checks the shared operation lock and current `origin/main`, ensures a recent authenticated MinIO recovery point, then invokes the existing **`deploy/deploy-release.sh`**. The deploy engine handles encrypted PostgreSQL backup, compatibility gates, migrations, application containers and smoke tests. **A short maintenance period may occur.** The script does not purge listing/media volumes. App rollback does not reverse irreversible migrations or payments.

**A green GitHub release is not a substitute for testing the actual changed behavior.** A merged commit and a running VPS build are different states; confirm the public fingerprint before announcing a release.

## Manual SSH deployment — exceptional operator fallback

Use this **only** for an explicitly authorized manual recovery or when the GitHub Actions route cannot be used after investigation. It is **not** the day-to-day workflow for contributors.

1. Confirm that a reviewed PR was merged into `main` and its final CI checks passed.
2. Confirm no release, rollback, backup or restore operation is running or holds the shared lock.
3. Connect to the **correct VPS**. Do **not** use the deprecated VPS `31.97.185.84`.
4. Fetch exact `origin/main`, prepare the immutable worktree, and run `deploy/deploy-release.sh` with the **matching complete SHA**.
5. Inspect `status=success`, active `current` SHA and public build fingerprint. Preserve incident logs on failure.

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
