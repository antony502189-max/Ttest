#!/usr/bin/env bash
set -euo pipefail
umask 077

# Run on the VPS with the dump path as $1. Only the throwaway verification DB is dropped.
[[ $# -eq 1 ]] || { echo "usage: $0 /absolute/path/to/backup.dump.enc" >&2; exit 64; }
ROOT="${ROOT:-/srv/112233.es}"
ENV_FILE="${ENV_FILE:-$ROOT/shared/production.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/current/docker-compose.production.yml}"
DUMP="$1"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/backup-crypto.sh
source "$SCRIPT_DIR/backup-crypto.sh"

[[ -f "$DUMP" && "$DUMP" == "$ROOT/backups/"*.dump.enc ]] || {
  echo "encrypted backup must be under $ROOT/backups" >&2
  exit 65
}
load_backup_keys "$ENV_FILE"
verify_backup_authentication "$DUMP"

user="$(sed -n 's/^POSTGRES_USER=//p' "$ENV_FILE" | tail -n 1)"
[[ "$user" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || { echo "invalid POSTGRES_USER" >&2; exit 65; }
db="restore_verify_$(date -u +%s)_$$_$RANDOM"
compose=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")
cleanup() { "${compose[@]}" exec -T postgres dropdb -U "$user" --if-exists --force "$db" || true; }
trap cleanup EXIT

"${compose[@]}" exec -T postgres createdb -U "$user" "$db"
openssl enc -d -aes-256-cbc -pbkdf2 -pass env:BACKUP_ENCRYPTION_KEY -in "$DUMP" \
  | "${compose[@]}" exec -T postgres pg_restore \
      -U "$user" -d "$db" --no-owner --no-privileges --exit-on-error --single-transaction
"${compose[@]}" exec -T postgres psql -v ON_ERROR_STOP=1 -U "$user" -d "$db" \
  -tAc 'SELECT PostGIS_Version(), count(*) FROM users;'
