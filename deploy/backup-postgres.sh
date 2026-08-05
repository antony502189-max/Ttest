#!/usr/bin/env bash
set -euo pipefail
umask 077

# Run on the VPS. This creates a new immutable dump; it never removes backups.
ROOT="${ROOT:-/srv/112233.es}"
ENV_FILE="${ENV_FILE:-$ROOT/shared/production.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/current/docker-compose.production.yml}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${RELEASE_LOCK_HELD:-0}" != "1" ]]; then
  command -v flock >/dev/null || { echo "flock is required for production backup serialization" >&2; exit 69; }
  exec 9>"$ROOT/shared/release.lock"
  chmod 600 "$ROOT/shared/release.lock"
  flock -n 9 || { echo "a production deploy, rollback, backup, or restore drill is already running" >&2; exit 75; }
  export RELEASE_LOCK_HELD=1
fi
# shellcheck source=deploy/backup-crypto.sh
source "$SCRIPT_DIR/backup-crypto.sh"
load_backup_keys "$ENV_FILE"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

stamp="$(date -u +%Y%m%d-%H%M%S)-$$-$RANDOM"
dump="$BACKUP_DIR/postgres-$stamp.dump.enc"
temporary_dump="$(mktemp "$BACKUP_DIR/.postgres-$stamp.XXXXXX.tmp")"
cleanup() { rm -f "$temporary_dump"; }
trap cleanup EXIT

compose=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")
for _ in $(seq 1 60); do
  if "${compose[@]}" exec -T postgres sh -ec 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
"${compose[@]}" exec -T postgres sh -ec 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null
"${compose[@]}" exec -T postgres \
  sh -ec 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
  | openssl enc -aes-256-cbc -pbkdf2 -salt \
      -pass env:BACKUP_ENCRYPTION_KEY -out "$temporary_dump"

[[ -s "$temporary_dump" ]] || { echo "PostgreSQL backup is empty" >&2; exit 65; }
chmod 600 "$temporary_dump"
mv "$temporary_dump" "$dump"
write_backup_hmac "$dump"
trap - EXIT
printf '%s\n' "$dump"
