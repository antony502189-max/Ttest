#!/usr/bin/env bash
set -euo pipefail
umask 077

# Recover the latest authenticated backup-set pointer directly from independent
# object storage, then download/authenticate its exact PostgreSQL+MinIO pair and
# restore only into throwaway verification targets. No VPS-local replication
# status is required, so this remains usable after total loss of the old VPS.
ROOT="${ROOT:-/srv/112233.es}"
ENV_FILE="${ENV_FILE:-$ROOT/shared/production.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/current/docker-compose.production.yml}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
DRILL_STATUS_FILE="${OFFSITE_RESTORE_STATUS_FILE:-$ROOT/shared/offsite-restore-drill.status}"
release_dir="$(dirname "$COMPOSE_FILE")"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

[[ -r "$ENV_FILE" ]] || { echo "production env is not readable: $ENV_FILE" >&2; exit 65; }
[[ -r "$COMPOSE_FILE" ]] || { echo "production compose file is not readable: $COMPOSE_FILE" >&2; exit 65; }
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

# shellcheck source=deploy/backup-crypto.sh
source "$SCRIPT_DIR/backup-crypto.sh"
load_backup_keys "$ENV_FILE"

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
manifest_value() {
  local key="$1"
  sed -n "s/^${key}=//p" "$manifest_local" | tail -n 1
}

endpoint="$(require_env OFFSITE_BACKUP_ENDPOINT)"
access_key="$(require_env OFFSITE_BACKUP_ACCESS_KEY)"
secret_key="$(require_env OFFSITE_BACKUP_SECRET_KEY)"
bucket="$(require_env OFFSITE_BACKUP_BUCKET)"
prefix="$(read_env OFFSITE_BACKUP_PREFIX)"
prefix="${prefix:-112233-production}"
[[ "$bucket" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "OFFSITE_BACKUP_BUCKET contains unsupported characters" >&2; exit 65; }
[[ "$prefix" != /* && "$prefix" != *..* ]] || { echo "OFFSITE_BACKUP_PREFIX must be a relative object prefix" >&2; exit 65; }

stamp="$(date -u +%Y%m%d-%H%M%S)-$$-$RANDOM"
manifest_local="$BACKUP_DIR/offsite-drill-set-$stamp.manifest"
postgres_local="$BACKUP_DIR/offsite-drill-postgres-$stamp.dump.enc"
minio_local="$BACKUP_DIR/offsite-drill-minio-$stamp.tar.enc"
cleanup() {
  rm -f \
    "$manifest_local" "$manifest_local.hmac" \
    "$postgres_local" "$postgres_local.hmac" \
    "$minio_local" "$minio_local.hmac"
}
trap cleanup EXIT

compose=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")
# Fetch only the fixed latest pointer first. It is untrusted until its HMAC is
# verified on the host; no filenames from it are acted upon before then.
"${compose[@]}" run --rm -T \
  -v "$BACKUP_DIR:/backups" \
  -e "OFFSITE_BACKUP_ENDPOINT=$endpoint" \
  -e "OFFSITE_BACKUP_ACCESS_KEY=$access_key" \
  -e "OFFSITE_BACKUP_SECRET_KEY=$secret_key" \
  -e "OFFSITE_BACKUP_BUCKET=$bucket" \
  -e "OFFSITE_BACKUP_PREFIX=$prefix" \
  -e "MANIFEST_LOCAL_FILE=${manifest_local##*/}" \
  --entrypoint /bin/sh offsite-tools -ec '
    mc alias set offsite "$OFFSITE_BACKUP_ENDPOINT" "$OFFSITE_BACKUP_ACCESS_KEY" "$OFFSITE_BACKUP_SECRET_KEY" >/dev/null
    source="offsite/$OFFSITE_BACKUP_BUCKET"
    if [ -n "$OFFSITE_BACKUP_PREFIX" ]; then
      source="$source/$OFFSITE_BACKUP_PREFIX"
    fi
    mc cp --quiet "$source/latest-backup-set.manifest" "/backups/$MANIFEST_LOCAL_FILE"
    mc cp --quiet "$source/latest-backup-set.manifest.hmac" "/backups/$MANIFEST_LOCAL_FILE.hmac"
  '
chmod 600 "$manifest_local" "$manifest_local.hmac"
verify_backup_authentication "$manifest_local"

declared_set="$(manifest_value backup_set_file)"
postgres_remote="$(manifest_value postgres_file)"
postgres_size="$(manifest_value postgres_size)"
minio_remote="$(manifest_value minio_file)"
minio_size="$(manifest_value minio_size)"
[[ "$declared_set" == backup-set-*.manifest && "$declared_set" != */* ]] || { echo "invalid authenticated backup-set identity" >&2; exit 65; }
[[ "$postgres_remote" == postgres-*.dump.enc && "$postgres_remote" != */* ]] || { echo "invalid authenticated PostgreSQL backup filename" >&2; exit 65; }
[[ "$minio_remote" == minio-*.tar.enc && "$minio_remote" != */* ]] || { echo "invalid authenticated MinIO backup filename" >&2; exit 65; }
[[ "$postgres_size" =~ ^[0-9]+$ && "$minio_size" =~ ^[0-9]+$ ]] || { echo "invalid authenticated backup sizes" >&2; exit 65; }

# Only after the pointer is authenticated do we use its unique object names.
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
  --entrypoint /bin/sh offsite-tools -ec '
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
[[ "$(stat -c %s "$postgres_local")" == "$postgres_size" ]] || { echo "downloaded PostgreSQL backup size does not match authenticated manifest" >&2; exit 65; }
[[ "$(stat -c %s "$minio_local")" == "$minio_size" ]] || { echo "downloaded MinIO backup size does not match authenticated manifest" >&2; exit 65; }
verify_backup_authentication "$postgres_local"
verify_backup_authentication "$minio_local"

ROOT="$ROOT" ENV_FILE="$ENV_FILE" COMPOSE_FILE="$COMPOSE_FILE" \
  "$release_dir/deploy/restore-verify.sh" "$postgres_local"
ROOT="$ROOT" ENV_FILE="$ENV_FILE" COMPOSE_FILE="$COMPOSE_FILE" \
  "$release_dir/deploy/restore-minio-verify.sh" "$minio_local"

mkdir -p "$(dirname "$DRILL_STATUS_FILE")"
temporary_status="$(mktemp "${DRILL_STATUS_FILE}.tmp.XXXXXX")"
{
  printf 'completed_at_epoch=%s\n' "$(date -u +%s)"
  printf 'backup_set_file=%s\n' "$declared_set"
  printf 'postgres_source=%s\n' "$postgres_remote"
  printf 'minio_source=%s\n' "$minio_remote"
} > "$temporary_status"
chmod 600 "$temporary_status"
mv -f "$temporary_status" "$DRILL_STATUS_FILE"
printf 'off-site restore drill passed: set=%s postgres=%s minio=%s\n' "$declared_set" "$postgres_remote" "$minio_remote"
