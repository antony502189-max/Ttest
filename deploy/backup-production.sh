#!/usr/bin/env bash
set -euo pipefail
umask 077

# Run both encrypted persistent-data backups. Neither child script deletes data.
ROOT="${ROOT:-/srv/112233.es}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/current/docker-compose.production.yml}"
ENV_FILE="${ENV_FILE:-$ROOT/shared/production.env}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
LOCK_FILE="$ROOT/shared/release.lock"
command -v flock >/dev/null || { echo "flock is required for production backup serialization" >&2; exit 69; }
exec 9>"$LOCK_FILE"
chmod 600 "$LOCK_FILE"
flock -n 9 || { echo "a production deploy, rollback, or backup is already running" >&2; exit 75; }
release_dir="$(dirname "$COMPOSE_FILE")"
COMPOSE_FILE="$COMPOSE_FILE" ENV_FILE="$ENV_FILE" BACKUP_DIR="$BACKUP_DIR" "$release_dir/deploy/backup-postgres.sh"
COMPOSE_FILE="$COMPOSE_FILE" ENV_FILE="$ENV_FILE" BACKUP_DIR="$BACKUP_DIR" "$release_dir/deploy/backup-minio.sh"
