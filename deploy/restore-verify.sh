#!/usr/bin/env bash
set -euo pipefail

# Run on the VPS with the dump path as $1. Only the throwaway verification DB is dropped.
[[ $# -eq 1 ]] || { echo "usage: $0 /absolute/path/to/backup.dump" >&2; exit 64; }
ROOT="${ROOT:-/srv/112233.es}"
ENV_FILE="${ENV_FILE:-$ROOT/shared/production.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/current/docker-compose.production.yml}"
DUMP="$1"
[[ -f "$DUMP" && "$DUMP" == "$ROOT/backups/"* ]] || { echo "backup must be under $ROOT/backups" >&2; exit 65; }
sha256sum -c "$DUMP.sha256"
user="$(grep '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2-)"
db="restore_verify_$(date -u +%s)"
cleanup() { docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T postgres dropdb -U "$user" --if-exists "$db" || true; }
trap cleanup EXIT
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T postgres createdb -U "$user" "$db"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T postgres pg_restore -U "$user" -d "$db" --no-owner --no-privileges < "$DUMP"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T postgres psql -U "$user" -d "$db" -tAc 'SELECT PostGIS_Version(), count(*) FROM users;'
