#!/usr/bin/env bash
set -euo pipefail
umask 077

# Roll back application code/images only. Persistent database, Redis and media
# volumes are never removed. With no argument, use the exact old_sha recorded
# for the current successful deployment; an explicit target SHA is reserved for
# recovery of installations that predate deployment metadata.
[[ $# -le 1 ]] || { echo "usage: $0 [target-release-sha]" >&2; exit 64; }
ROOT="${ROOT:-/srv/112233.es}"
ENV_FILE="$ROOT/shared/production.env"
CURRENT="$ROOT/current"
LOCK_FILE="$ROOT/shared/release.lock"
[[ -r "$ENV_FILE" ]] || { echo "missing $ENV_FILE" >&2; exit 65; }
[[ "$(stat -c %a "$ENV_FILE")" == "600" ]] || { echo "$ENV_FILE must have mode 600" >&2; exit 65; }
command -v flock >/dev/null || { echo "flock is required for production release serialization" >&2; exit 69; }
exec 9>"$LOCK_FILE"
chmod 600 "$LOCK_FILE"
flock -n 9 || { echo "another production deploy or rollback is already running" >&2; exit 75; }
[[ -L "$CURRENT" ]] || { echo "no current release" >&2; exit 65; }
current="$(readlink -f "$CURRENT")"
current_sha="$(basename "$current")"
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
previous="$ROOT/releases/$target_sha"
[[ -f "$previous/docker-compose.production.yml" ]] || {
  echo "target release is unavailable: $previous" >&2
  exit 65
}

compose=(docker compose --env-file "$ENV_FILE" -f "$previous/docker-compose.production.yml")
"${compose[@]}" config --quiet

restore_current_after_failure() {
  local exit_code=$?
  trap - ERR
  set +e
  echo "rollback target failed readiness; restoring current release $current_sha" >&2
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

"${compose[@]}" up -d --build backend mail-worker external-listings-worker frontend
for _ in $(seq 1 30); do
  if "${compose[@]}" exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready', timeout=3)"; then break; fi
  sleep 2
done
"${compose[@]}" exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready', timeout=3)"
ln -sfn "$previous" "$CURRENT"
trap - ERR
printf 'rolled back from %s to %s\n' "$current_sha" "$target_sha"
