#!/usr/bin/env bash
set -euo pipefail
umask 077

# Run both encrypted persistent-data backups under one release lock and publish
# an authenticated manifest only after both artifacts completed successfully.
# Neither child script deletes data.
ROOT="${ROOT:-/srv/112233.es}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/current/docker-compose.production.yml}"
ENV_FILE="${ENV_FILE:-$ROOT/shared/production.env}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
LOCK_FILE="$ROOT/shared/release.lock"
release_dir="$(dirname "$COMPOSE_FILE")"
command -v flock >/dev/null || { echo "flock is required for production backup serialization" >&2; exit 69; }
exec 9>"$LOCK_FILE"
chmod 600 "$LOCK_FILE"
flock -n 9 || { echo "a production deploy, rollback, backup, or restore drill is already running" >&2; exit 75; }
export RELEASE_LOCK_HELD=1

postgres_backup="$(
  COMPOSE_FILE="$COMPOSE_FILE" ENV_FILE="$ENV_FILE" BACKUP_DIR="$BACKUP_DIR" \
    "$release_dir/deploy/backup-postgres.sh"
)"
minio_backup="$(
  COMPOSE_FILE="$COMPOSE_FILE" ENV_FILE="$ENV_FILE" BACKUP_DIR="$BACKUP_DIR" \
    "$release_dir/deploy/backup-minio.sh"
)"

[[ -f "$postgres_backup" && "$postgres_backup" == "$BACKUP_DIR/"postgres-*.dump.enc ]] || {
  echo "PostgreSQL backup child returned an invalid artifact path" >&2
  exit 65
}
[[ -f "$minio_backup" && "$minio_backup" == "$BACKUP_DIR/"minio-*.tar.enc ]] || {
  echo "MinIO backup child returned an invalid artifact path" >&2
  exit 65
}
[[ -f "$postgres_backup.hmac" && -f "$minio_backup.hmac" ]] || {
  echo "backup set cannot be published without both authenticated artifacts" >&2
  exit 65
}

# shellcheck source=deploy/backup-crypto.sh
source "$release_dir/deploy/backup-crypto.sh"
load_backup_keys "$ENV_FILE"
verify_backup_authentication "$postgres_backup"
verify_backup_authentication "$minio_backup"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
stamp="$(date -u +%Y%m%d-%H%M%S)-$$-$RANDOM"
manifest="$BACKUP_DIR/backup-set-$stamp.manifest"
manifest_name="${manifest##*/}"
temporary_manifest="$(mktemp "$BACKUP_DIR/.backup-set-$stamp.XXXXXX.tmp")"
cleanup() { rm -f "$temporary_manifest"; }
trap cleanup EXIT
{
  printf 'created_at_epoch=%s\n' "$(date -u +%s)"
  printf 'backup_set_file=%s\n' "$manifest_name"
  printf 'postgres_file=%s\n' "${postgres_backup##*/}"
  printf 'postgres_size=%s\n' "$(stat -c %s "$postgres_backup")"
  printf 'minio_file=%s\n' "${minio_backup##*/}"
  printf 'minio_size=%s\n' "$(stat -c %s "$minio_backup")"
} > "$temporary_manifest"
chmod 600 "$temporary_manifest"
mv "$temporary_manifest" "$manifest"
write_backup_hmac "$manifest"
trap - EXIT
printf '%s\n' "$manifest"
