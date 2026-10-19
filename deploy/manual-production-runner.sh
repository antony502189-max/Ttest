#!/usr/bin/env bash
# Install a reviewed, root-owned copy as:
#   /usr/local/sbin/112233-manual-production-deploy (mode 0700)
# Restrict the GitHub Actions public SSH key with:
#   command="/usr/local/sbin/112233-manual-production-deploy",restrict
set -Eeuo pipefail
umask 077

ROOT=/srv/112233.es
SELF=/usr/local/sbin/112233-manual-production-deploy

test "$(id -u)" = "0"
test "$(hostname)" = "vmi3640228"

if [[ $# -eq 0 ]]; then
  remote_command="$(printenv SSH_ORIGINAL_COMMAND || true)"
  if [[ ! "$remote_command" =~ ^deploy[[:space:]]([0-9a-f]{40})$ ]]; then
    echo "Denied: only 'deploy <40-character-main-sha>' is allowed" >&2
    exit 64
  fi
  SHA="${BASH_REMATCH[1]}"
  command -v systemd-run >/dev/null || { echo "systemd-run is required"; exit 69; }
  echo "Starting a server-managed release for $SHA"
  # A transient systemd service survives an interrupted SSH connection.
  # Do not launch a second deployment while the existing unit/lock is active.
  systemd-run --wait --collect --property=Type=exec \
    --property=TimeoutStartSec=0 \
    --unit="112233-release-$SHA" "$SELF" --internal "$SHA"
  test "$(readlink -f "$ROOT/current")" = "$ROOT/releases/$SHA"
  grep -Fxq 'status=success' "$ROOT/releases/$SHA.deploy-info"
  echo "DEPLOY SUCCESS: $SHA"
  exit 0
fi

# Only the trusted systemd service may invoke the internal entrypoint.
if [[ $# -ne 2 || "$1" != "--internal" || ! "$2" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Denied: unsupported internal invocation" >&2
  exit 64
fi
if [[ -z "$(printenv INVOCATION_ID || true)" ]]; then
  echo "Denied: internal runner must be started by systemd" >&2
  exit 64
fi

SHA="$2"
RELEASE="$ROOT/releases/$SHA"
ENV_FILE="$ROOT/shared/production.env"
LOCK_FILE="$ROOT/shared/release.lock"

test -L "$ROOT/current"
test -d "$ROOT/repo/.git"
test "$(stat -c %a "$ENV_FILE")" = "600"
command -v flock >/dev/null

# Refuse concurrent manual and automated backup/deploy/rollback operations.
if ! flock -n "$LOCK_FILE" true; then
  echo "Another production operation holds the shared release lock" >&2
  exit 75
fi

# A noninteractive VPS -> GitHub read-only Deploy Key is required.
export GIT_TERMINAL_PROMPT=0
export GCM_INTERACTIVE=Never
origin="$(git -C "$ROOT/repo" remote get-url origin)"
case "$origin" in
  https://github.com/antony502189-max/Ttest|https://github.com/antony502189-max/Ttest.git|git@github.com:antony502189-max/Ttest|git@github.com:antony502189-max/Ttest.git) ;;
  *) echo "Unexpected production repository origin" >&2; exit 65 ;;
esac

echo "Checking the approved origin/main SHA: $SHA"
git -C "$ROOT/repo" fetch origin --prune --tags
actual="$(git -C "$ROOT/repo" rev-parse --verify origin/main)"
if [[ "$actual" != "$SHA" ]]; then
  echo "origin/main changed since approval; refusing stale deployment" >&2
  exit 65
fi

if [[ "$(readlink -f "$ROOT/current")" == "$RELEASE" ]]; then
  echo "Release already active; running smoke check"
  ROOT="$ROOT" bash "$ROOT/current/deploy/smoke-production.sh"
  exit 0
fi

# The original deploy-release.sh checks the authenticated MinIO backup
# independently before it stops writers. This step prepares a fresh point
# using CURRENT released code, never the candidate's untested backup logic.
if ! bash "$ROOT/current/deploy/require-fresh-minio-backup.sh" >/dev/null; then
  echo "No recent authenticated MinIO backup; creating it with current release"
  bash "$ROOT/current/deploy/backup-minio.sh"
  bash "$ROOT/current/deploy/require-fresh-minio-backup.sh" >/dev/null
fi

if [[ ! -e "$RELEASE/.git" ]]; then
  git -C "$ROOT/repo" worktree add --detach "$RELEASE" "$SHA"
fi

echo "Launching the existing audited deploy engine for $SHA"
ROOT="$ROOT" bash "$RELEASE/deploy/deploy-release.sh" "$SHA"
test "$(readlink -f "$ROOT/current")" = "$RELEASE"
grep -Fxq 'status=success' "$ROOT/releases/$SHA.deploy-info"
ROOT="$ROOT" bash "$ROOT/current/deploy/smoke-production.sh"
echo "DEPLOY SUCCESS: $SHA"
