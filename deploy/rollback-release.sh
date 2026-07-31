#!/usr/bin/env bash
set -euo pipefail

# Roll back application code/images only. Persistent database, Redis and media volumes are never removed.
ROOT="${ROOT:-/srv/112233.es}"
ENV_FILE="$ROOT/shared/production.env"
CURRENT="$ROOT/current"
[[ -L "$CURRENT" ]] || { echo "no current release" >&2; exit 65; }
current="$(readlink -f "$CURRENT")"
previous="$(find "$ROOT/releases" -mindepth 1 -maxdepth 1 -type d ! -samefile "$current" -printf '%T@ %p\n' | sort -nr | head -1 | cut -d' ' -f2-)"
[[ -n "$previous" ]] || { echo "no previous release to roll back to" >&2; exit 65; }
compose=(docker compose --env-file "$ENV_FILE" -f "$previous/docker-compose.production.yml")
"${compose[@]}" config --quiet
"${compose[@]}" up -d --build backend mail-worker external-listings-worker frontend
"${compose[@]}" exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready', timeout=3)"
ln -sfn "$previous" "$CURRENT"
printf 'rolled back to %s\n' "$(basename "$previous")"
