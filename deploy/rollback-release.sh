#!/usr/bin/env bash
set -euo pipefail
umask 077

# Roll back application code/images only. Persistent database, Redis and media
# volumes are never removed. With no argument, use the exact old_sha recorded
# for the current successful deployment; an explicit target SHA is reserved for
# recovery of installations that predate deployment metadata.
[[ $# -le 1 ]] || { echo "usage: $0 [target-release-sha]" >&2; exit 64; }
ROOT="${ROOT:-/srv/112233.es}"
REPO="$ROOT/repo"
RELEASES="$ROOT/releases"
ENV_FILE="$ROOT/shared/production.env"
CURRENT="$ROOT/current"
LOCK_FILE="$ROOT/shared/release.lock"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

verify_release_worktree() {
  local path="$1" expected_sha="$2"
  local actual_sha common_dir expected_common dirty
  [[ "$(readlink -f "$path")" == "$(readlink -f "$RELEASES/$expected_sha")" ]] || {
    echo "release path does not match its expected immutable location: $path" >&2
    return 65
  }
  [[ -e "$path/.git" ]] || { echo "release is not a Git worktree: $path" >&2; return 65; }
  actual_sha="$(git -C "$path" rev-parse --verify HEAD)"
  [[ "$actual_sha" == "$expected_sha" ]] || {
    echo "release HEAD mismatch: expected $expected_sha, found $actual_sha" >&2
    return 65
  }
  common_dir="$(git -C "$path" rev-parse --git-common-dir)"
  [[ "$common_dir" == /* ]] || common_dir="$path/$common_dir"
  common_dir="$(readlink -f "$common_dir")"
  expected_common="$(readlink -f "$REPO/.git")"
  [[ "$common_dir" == "$expected_common" ]] || {
    echo "release worktree is not attached to the production repository: $path" >&2
    return 65
  }
  dirty="$(git -C "$path" status --porcelain --untracked-files=all)"
  [[ -z "$dirty" ]] || {
    echo "release worktree is not immutable and clean: $path" >&2
    printf '%s\n' "$dirty" >&2
    return 65
  }
}

[[ -r "$ENV_FILE" ]] || { echo "missing $ENV_FILE" >&2; exit 65; }
[[ "$(stat -c %a "$ENV_FILE")" == "600" ]] || { echo "$ENV_FILE must have mode 600" >&2; exit 65; }
[[ -d "$REPO/.git" ]] || { echo "missing production repository: $REPO" >&2; exit 65; }
command -v flock >/dev/null || { echo "flock is required for production release serialization" >&2; exit 69; }
exec 9>"$LOCK_FILE"
chmod 600 "$LOCK_FILE"
flock -n 9 || { echo "another production deploy or rollback is already running" >&2; exit 75; }
[[ -L "$CURRENT" ]] || { echo "no current release" >&2; exit 65; }
current="$(readlink -f "$CURRENT")"
current_sha="$(basename "$current")"
[[ "$current_sha" =~ ^[0-9a-f]{40}$ ]] || { echo "current release directory is not a full commit SHA" >&2; exit 65; }
verify_release_worktree "$current" "$current_sha"
current_compose=(docker compose --env-file "$ENV_FILE" -f "$current/docker-compose.production.yml")
"${current_compose[@]}" config --quiet

if [[ $# -eq 1 ]]; then
  target_sha="$1"
else
  metadata="$ROOT/releases/$current_sha.deploy-info"
  [[ -r "$metadata" ]] || {
    echo "missing deployment metadata for $current_sha; provide an explicit target SHA" >&2
    exit 65
  }
  target_sha="$(sed -n 's/^old_sha=//p' "$metadata" | tail -1)"
fi

[[ "$target_sha" =~ ^[0-9a-f]{40}$ ]] || {
  echo "no valid previous release SHA is recorded; provide an explicit 40-character target SHA" >&2
  exit 65
}
[[ "$target_sha" != "$current_sha" ]] || { echo "target release is already current" >&2; exit 65; }
previous="$RELEASES/$target_sha"
[[ -f "$previous/docker-compose.production.yml" ]] || {
  echo "target release is unavailable: $previous" >&2
  exit 65
}
verify_release_worktree "$previous" "$target_sha"

compose=(docker compose --env-file "$ENV_FILE" -f "$previous/docker-compose.production.yml")
"${compose[@]}" config --quiet
current_data_images="$("${current_compose[@]}" config --format json | python3 "$SCRIPT_DIR/data-service-images.py")"
target_data_images="$("${compose[@]}" config --format json | python3 "$SCRIPT_DIR/data-service-images.py")"
[[ "$target_data_images" == "$current_data_images" ]] || {
  echo "rollback across stateful service image changes requires a separate controlled data-service recovery" >&2
  diff -u <(printf '%s\n' "$current_data_images") <(printf '%s\n' "$target_data_images") >&2 || true
  exit 65
}

restore_current_after_failure() {
  local exit_code=$?
  trap - ERR
  set +e
  echo "rollback target failed readiness; restoring current release $current_sha" >&2
  "${current_compose[@]}" up -d postgres redis minio minio-init
  "${current_compose[@]}" up -d --build backend mail-worker external-listings-worker frontend
  restored=0
  for _ in $(seq 1 30); do
    if "${current_compose[@]}" exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready', timeout=3)"; then
      restored=1
      break
    fi
    sleep 2
  done
  if (( ! restored )); then
    echo "current release also failed readiness; manual incident response is required" >&2
  fi
  exit "$exit_code"
}
trap restore_current_after_failure ERR

"${compose[@]}" up -d postgres redis minio minio-init
"${compose[@]}" up -d --build backend mail-worker external-listings-worker frontend
for _ in $(seq 1 30); do
  if "${compose[@]}" exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready', timeout=3)"; then break; fi
  sleep 2
done
"${compose[@]}" exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready', timeout=3)"
ln -sfn "$previous" "$CURRENT"
trap - ERR
printf 'rolled back from %s to %s\n' "$current_sha" "$target_sha"
