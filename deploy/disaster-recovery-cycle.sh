#!/usr/bin/env bash
set -euo pipefail
umask 077

# Produce fresh authenticated local backups first, then replicate the completed
# immutable artifacts off the VPS. The local backup phase owns the release lock;
# off-site transfer starts only after that process exits and never deletes data.
ROOT="${ROOT:-/srv/112233.es}"
ENV_FILE="${ENV_FILE:-$ROOT/shared/production.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/current/docker-compose.production.yml}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
release_dir="$(dirname "$COMPOSE_FILE")"

ROOT="$ROOT" ENV_FILE="$ENV_FILE" COMPOSE_FILE="$COMPOSE_FILE" BACKUP_DIR="$BACKUP_DIR" \
  "$release_dir/deploy/backup-production.sh"
ROOT="$ROOT" ENV_FILE="$ENV_FILE" COMPOSE_FILE="$COMPOSE_FILE" BACKUP_DIR="$BACKUP_DIR" \
  "$release_dir/deploy/offsite-backup-sync.sh"
