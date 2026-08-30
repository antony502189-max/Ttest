#!/usr/bin/env bash
set -euo pipefail
umask 077

# Produce a fresh authenticated PostgreSQL+MinIO backup set first, then
# replicate that exact set off the VPS. The local backup phase owns the release
# lock; off-site transfer starts only after the set manifest is durable and
# never deletes local or remote data.
ROOT="${ROOT:-/srv/112233.es}"
ENV_FILE="${ENV_FILE:-$ROOT/shared/production.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/current/docker-compose.production.yml}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
release_dir="$(dirname "$COMPOSE_FILE")"

backup_set="$(
  ROOT="$ROOT" ENV_FILE="$ENV_FILE" COMPOSE_FILE="$COMPOSE_FILE" BACKUP_DIR="$BACKUP_DIR" \
    "$release_dir/deploy/backup-production.sh"
)"
[[ -f "$backup_set" && "$backup_set" == "$BACKUP_DIR/"backup-set-*.manifest ]] || {
  echo "backup-production did not return a valid completed backup set" >&2
  exit 65
}
ROOT="$ROOT" ENV_FILE="$ENV_FILE" COMPOSE_FILE="$COMPOSE_FILE" BACKUP_DIR="$BACKUP_DIR" \
  BACKUP_SET_MANIFEST="$backup_set" \
  "$release_dir/deploy/offsite-backup-sync.sh"
