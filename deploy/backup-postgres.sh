#!/usr/bin/env bash
set -euo pipefail

# Run on the VPS. This creates a new immutable dump; it never removes backups.
ROOT="${ROOT:-/srv/112233.es}"
ENV_FILE="${ENV_FILE:-$ROOT/shared/production.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/current/docker-compose.production.yml}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
[[ -r "$ENV_FILE" ]] || { echo "missing $ENV_FILE" >&2; exit 65; }
BACKUP_ENCRYPTION_KEY="$(grep '^BACKUP_ENCRYPTION_KEY=' "$ENV_FILE" | cut -d= -f2-)"
export BACKUP_ENCRYPTION_KEY
[[ -n "$BACKUP_ENCRYPTION_KEY" ]] || { echo "BACKUP_ENCRYPTION_KEY is required" >&2; exit 65; }
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

stamp="$(date -u +%Y%m%d-%H%M%S)"
dump="$BACKUP_DIR/postgres-$stamp.dump.enc"
checksum="$dump.sha256"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T postgres \
  pg_dump -U "$(grep '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2-)" \
  -d "$(grep '^POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2-)" --format=custom \
  | openssl enc -aes-256-cbc -pbkdf2 -salt -pass env:BACKUP_ENCRYPTION_KEY -out "$dump"
sha256sum "$dump" > "$checksum"
chmod 600 "$dump" "$checksum"
printf '%s\n' "$dump"
