#!/usr/bin/env bash
set -euo pipefail
umask 077

# Download the exact pair recorded by the most recent successful off-site sync,
# authenticate both ciphertexts, and restore them only into throwaway PostgreSQL
# and MinIO targets using the existing verification scripts. Production data is
# never overwritten by this drill.
ROOT="${ROOT:-/srv/112233.es}"
ENV_FILE="${ENV_FILE:-$ROOT/shared/production.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/current/docker-compose.production.yml}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
STATUS_FILE="${OFFSITE_BACKUP_STATUS_FILE:-$ROOT/shared/offsite-backup.status}"
DRILL_STATUS_FILE="${OFFSITE_RESTORE_STATUS_FILE:-$ROOT/shared/offsite-restore-drill.status}"
release_dir="$(dirname "$COMPOSE_FILE")"

[[ -r "$STATUS_FILE" ]] || { echo "off-site backup status is missing: $STATUS_FILE" >&2; exit 65; }
[[ -r "$ENV_FILE" ]] || { echo "production env is not readable: $ENV_FILE" >&2; exit 65; }
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

read_status() {
  local key="$1"
  sed -n "s/^${key}=//p" "$STATUS_FILE" | tail -n 1
}
read_env() {
  local key="$1"
  sed -n "s/^${key}=//p" "$ENV_FILE" | tail -n 1
}
require_env() {
  local key="$1" value
  value="$(read_env "$key")"
  [[ -n "$value" ]] || { echo "$key is required for off-site restore verification" >&2; exit 65; }
  printf '%s' "$value"
}

postgres_remote="$(read_status postgres_file)"
minio_remote="$(read_status minio_file)"
bucket="$(read_status remote_bucket)"
prefix="$(read_status remote_prefix)"
[[ "$postgres_remote" == postgres-*.dump.enc ]] || { echo "invalid PostgreSQL off-site status filename" >&2; exit 65; }
[[ "$minio_remote" == minio-*.tar.enc ]] || { echo "invalid MinIO off-site status filename" >&2; exit 65; }
[[ "$bucket" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "invalid off-site bucket in status file" >&2; exit 65; }
[[ "$prefix" != /* && "$prefix" != *..* ]] || { echo "invalid off-site prefix in status file" >&2; exit 65; }

endpoint="$(require_env OFFSITE_BACKUP_ENDPOINT)"
access_key="$(require_env OFFSITE_BACKUP_ACCESS_KEY)"
secret_key="$(require_env OFFSITE_BACKUP_SECRET_KEY)"

stamp="$(date -u +%Y%m%d-%H%M%S)-$$-$RANDOM"
postgres_local="$BACKUP_DIR/offsite-drill-postgres-$stamp.dump.enc"
minio_local="$BACKUP_DIR/offsite-drill-minio-$stamp.tar.enc"
cleanup() {
  rm -f \
    "$postgres_local" "$postgres_local.hmac" \
    "$minio_local" "$minio_local.hmac"
}
trap cleanup EXIT

compose=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")
"${compose[@]}" run --rm -T \
  -v "$BACKUP_DIR:/backups" \
  -e "OFFSITE_BACKUP_ENDPOINT=$endpoint" \
  -e "OFFSITE_BACKUP_ACCESS_KEY=$access_key" \
  -e "OFFSITE_BACKUP_SECRET_KEY=$secret_key" \
  -e "OFFSITE_BACKUP_BUCKET=$bucket" \
  -e "OFFSITE_BACKUP_PREFIX=$prefix" \
  -e "POSTGRES_REMOTE_FILE=$postgres_remote" \
  -e "MINIO_REMOTE_FILE=$minio_remote" \
  -e "POSTGRES_LOCAL_FILE=${postgres_local##*/}" \
  -e "MINIO_LOCAL_FILE=${minio_local##*/}" \
  --entrypoint /bin/sh minio-init -ec '
    mc alias set offsite "$OFFSITE_BACKUP_ENDPOINT" "$OFFSITE_BACKUP_ACCESS_KEY" "$OFFSITE_BACKUP_SECRET_KEY" >/dev/null
    source="offsite/$OFFSITE_BACKUP_BUCKET"
    if [ -n "$OFFSITE_BACKUP_PREFIX" ]; then
      source="$source/$OFFSITE_BACKUP_PREFIX"
    fi
    mc cp --quiet "$source/$POSTGRES_REMOTE_FILE" "/backups/$POSTGRES_LOCAL_FILE"
    mc cp --quiet "$source/$POSTGRES_REMOTE_FILE.hmac" "/backups/$POSTGRES_LOCAL_FILE.hmac"
    mc cp --quiet "$source/$MINIO_REMOTE_FILE" "/backups/$MINIO_LOCAL_FILE"
    mc cp --quiet "$source/$MINIO_REMOTE_FILE.hmac" "/backups/$MINIO_LOCAL_FILE.hmac"
  '

chmod 600 \
  "$postgres_local" "$postgres_local.hmac" \
  "$minio_local" "$minio_local.hmac"

ROOT="$ROOT" ENV_FILE="$ENV_FILE" COMPOSE_FILE="$COMPOSE_FILE" \
  "$release_dir/deploy/restore-verify.sh" "$postgres_local"
ROOT="$ROOT" ENV_FILE="$ENV_FILE" COMPOSE_FILE="$COMPOSE_FILE" \
  "$release_dir/deploy/restore-minio-verify.sh" "$minio_local"

mkdir -p "$(dirname "$DRILL_STATUS_FILE")"
temporary_status="$(mktemp "${DRILL_STATUS_FILE}.tmp.XXXXXX")"
{
  printf 'completed_at_epoch=%s\n' "$(date -u +%s)"
  printf 'postgres_source=%s\n' "$postgres_remote"
  printf 'minio_source=%s\n' "$minio_remote"
} > "$temporary_status"
chmod 600 "$temporary_status"
mv -f "$temporary_status" "$DRILL_STATUS_FILE"
printf 'off-site restore drill passed: postgres=%s minio=%s\n' "$postgres_remote" "$minio_remote"
