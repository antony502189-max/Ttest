#!/usr/bin/env bash
set -euo pipefail

# Roll back application code/images only. Persistent database, Redis and media
# volumes are never removed. With no argument, use the exact old_sha recorded
# for the current successful deployment; an explicit target SHA is reserved for
# recovery of installations that predate deployment metadata.
[[ $# -le 1 ]] || { echo "usage: $0 [target-release-sha]" >&2; exit 64; }
ROOT="${ROOT:-/srv/112233.es}"
ENV_FILE="$ROOT/shared/production.env"
CURRENT="$ROOT/current"
[[ -L "$CURRENT" ]] || { echo "no current release" >&2; exit 65; }
current="$(readlink -f "$CURRENT")"
current_sha="$(basename "$current")"

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
"${compose[@]}" up -d --build backend mail-worker external-listings-worker frontend
"${compose[@]}" exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready', timeout=3)"
ln -sfn "$previous" "$CURRENT"
printf 'rolled back from %s to %s\n' "$current_sha" "$target_sha"
