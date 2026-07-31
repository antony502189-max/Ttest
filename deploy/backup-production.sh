#!/usr/bin/env bash
set -euo pipefail

# Run both encrypted persistent-data backups. Neither child script deletes data.
ROOT="${ROOT:-/srv/112233.es}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/current/docker-compose.production.yml}"
ENV_FILE="${ENV_FILE:-$ROOT/shared/production.env}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
release_dir="$(dirname "$COMPOSE_FILE")"
COMPOSE_FILE="$COMPOSE_FILE" ENV_FILE="$ENV_FILE" BACKUP_DIR="$BACKUP_DIR" "$release_dir/deploy/backup-postgres.sh"
COMPOSE_FILE="$COMPOSE_FILE" ENV_FILE="$ENV_FILE" BACKUP_DIR="$BACKUP_DIR" "$release_dir/deploy/backup-minio.sh"
