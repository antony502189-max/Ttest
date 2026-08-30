#!/usr/bin/env bash
set -euo pipefail
umask 077

# Replicate one authenticated PostgreSQL+MinIO backup set to an independent
# S3-compatible bucket. This script never deletes local or remote data. Remote
# retention/versioning/object-lock policy belongs to the storage provider.
ROOT="${ROOT:-/srv/112233.es}"
ENV_FILE="${ENV_FILE:-$ROOT/shared/production.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/current/docker-compose.production.yml}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
STATUS_FILE="${OFFSITE_BACKUP_STATUS_FILE:-$ROOT/shared/offsite-backup.status}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

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
  [[ -n "$value" ]] || { echo "$key is required for off-site backup replication" >&2; exit 65; }
  printf '%s' "$value"
}

manifest_value() {
  local key="$1"
  sed -n "s/^${key}=//p" "$manifest" | tail -n 1
}

endpoint="$(require_env OFFSITE_BACKUP_ENDPOINT)"
access_key="$(require_env OFFSITE_BACKUP_ACCESS_KEY)"
secret_key="$(require_env OFFSITE_BACKUP_SECRET_KEY)"
bucket="$(require_env OFFSITE_BACKUP_BUCKET)"
prefix="$(read_env OFFSITE_BACKUP_PREFIX)"
prefix="${prefix:-112233-production}"

[[ "$bucket" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "OFFSITE_BACKUP_BUCKET contains unsupported characters" >&2; exit 65; }
[[ "$prefix" != /* && "$prefix" != *..* ]] || { echo "OFFSITE_BACKUP_PREFIX must be a relative object prefix" >&2; exit 65; }
[[ -d "$BACKUP_DIR" ]] || { echo "backup directory does not exist: $BACKUP_DIR" >&2; exit 65; }
[[ -r "$COMPOSE_FILE" ]] || { echo "production compose file is not readable: $COMPOSE_FILE" >&2; exit 65; }

manifest="${BACKUP_SET_MANIFEST:-}"
if [[ -z "$manifest" ]]; then
  manifest="$(
    find "$BACKUP_DIR" -maxdepth 1 -type f -name 'backup-set-*.manifest' -printf '%T@ %p\n' \
      | sort -nr \
      | head -n 1 \
      | cut -d' ' -f2-
  )"
fi
[[ -n "$manifest" && -f "$manifest" && "$manifest" == "$BACKUP_DIR/"backup-set-*.manifest ]] || {
  echo "an authenticated backup-set manifest under $BACKUP_DIR is required" >&2
  exit 65
}
verify_backup_authentication "$manifest"

postgres_name="$(manifest_value postgres_file)"
postgres_size="$(manifest_value postgres_size)"
minio_name="$(manifest_value minio_file)"
minio_size="$(manifest_value minio_size)"
manifest_name="${manifest##*/}"

[[ "$postgres_name" == postgres-*.dump.enc && "$postgres_name" != */* ]] || { echo "invalid PostgreSQL backup-set filename" >&2; exit 65; }
[[ "$minio_name" == minio-*.tar.enc && "$minio_name" != */* ]] || { echo "invalid MinIO backup-set filename" >&2; exit 65; }
[[ "$postgres_size" =~ ^[0-9]+$ && "$minio_size" =~ ^[0-9]+$ ]] || { echo "invalid backup-set sizes" >&2; exit 65; }
postgres_backup="$BACKUP_DIR/$postgres_name"
minio_backup="$BACKUP_DIR/$minio_name"
[[ -f "$postgres_backup" && -f "$postgres_backup.hmac" ]] || { echo "backup-set PostgreSQL artifact is incomplete" >&2; exit 65; }
[[ -f "$minio_backup" && -f "$minio_backup.hmac" ]] || { echo "backup-set MinIO artifact is incomplete" >&2; exit 65; }
[[ "$(stat -c %s "$postgres_backup")" == "$postgres_size" ]] || { echo "PostgreSQL backup-set size changed after manifest creation" >&2; exit 65; }
[[ "$(stat -c %s "$minio_backup")" == "$minio_size" ]] || { echo "MinIO backup-set size changed after manifest creation" >&2; exit 65; }
verify_backup_authentication "$postgres_backup"
verify_backup_authentication "$minio_backup"

postgres_hmac_size="$(stat -c %s "$postgres_backup.hmac")"
minio_hmac_size="$(stat -c %s "$minio_backup.hmac")"
manifest_size="$(stat -c %s "$manifest")"
manifest_hmac_size="$(stat -c %s "$manifest.hmac")"

compose=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")
"${compose[@]}" run --rm -T \
  -v "$BACKUP_DIR:/backups:ro" \
  -e "OFFSITE_BACKUP_ENDPOINT=$endpoint" \
  -e "OFFSITE_BACKUP_ACCESS_KEY=$access_key" \
  -e "OFFSITE_BACKUP_SECRET_KEY=$secret_key" \
  -e "OFFSITE_BACKUP_BUCKET=$bucket" \
  -e "OFFSITE_BACKUP_PREFIX=$prefix" \
  -e "POSTGRES_BACKUP_FILE=$postgres_name" \
  -e "POSTGRES_BACKUP_SIZE=$postgres_size" \
  -e "POSTGRES_HMAC_SIZE=$postgres_hmac_size" \
  -e "MINIO_BACKUP_FILE=$minio_name" \
  -e "MINIO_BACKUP_SIZE=$minio_size" \
  -e "MINIO_HMAC_SIZE=$minio_hmac_size" \
  -e "BACKUP_SET_FILE=$manifest_name" \
  -e "BACKUP_SET_SIZE=$manifest_size" \
  -e "BACKUP_SET_HMAC_SIZE=$manifest_hmac_size" \
  --entrypoint /bin/sh offsite-tools -ec '
    mc alias set offsite "$OFFSITE_BACKUP_ENDPOINT" "$OFFSITE_BACKUP_ACCESS_KEY" "$OFFSITE_BACKUP_SECRET_KEY" >/dev/null
    mc stat "offsite/$OFFSITE_BACKUP_BUCKET" >/dev/null
    target="offsite/$OFFSITE_BACKUP_BUCKET"
    if [ -n "$OFFSITE_BACKUP_PREFIX" ]; then
      target="$target/$OFFSITE_BACKUP_PREFIX"
    fi

    verify_remote_size() {
      file="$1"
      expected="$2"
      remote_size="$(mc stat --json "$target/$file" | busybox sed -n "s/.*\"size\":\([0-9][0-9]*\).*/\1/p" | busybox tail -n 1)"
      [ -n "$remote_size" ] || { echo "unable to read remote size for $file" >&2; exit 65; }
      [ "$remote_size" = "$expected" ] || {
        echo "remote size mismatch for $file: expected $expected, got $remote_size" >&2
        exit 65
      }
    }

    for file in \
      "$POSTGRES_BACKUP_FILE" "$POSTGRES_BACKUP_FILE.hmac" \
      "$MINIO_BACKUP_FILE" "$MINIO_BACKUP_FILE.hmac" \
      "$BACKUP_SET_FILE" "$BACKUP_SET_FILE.hmac"; do
      mc cp --quiet "/backups/$file" "$target/$file"
    done

    verify_remote_size "$POSTGRES_BACKUP_FILE" "$POSTGRES_BACKUP_SIZE"
    verify_remote_size "$POSTGRES_BACKUP_FILE.hmac" "$POSTGRES_HMAC_SIZE"
    verify_remote_size "$MINIO_BACKUP_FILE" "$MINIO_BACKUP_SIZE"
    verify_remote_size "$MINIO_BACKUP_FILE.hmac" "$MINIO_HMAC_SIZE"
    verify_remote_size "$BACKUP_SET_FILE" "$BACKUP_SET_SIZE"
    verify_remote_size "$BACKUP_SET_FILE.hmac" "$BACKUP_SET_HMAC_SIZE"
  '

mkdir -p "$(dirname "$STATUS_FILE")"
temporary_status="$(mktemp "${STATUS_FILE}.tmp.XXXXXX")"
{
  printf 'completed_at_epoch=%s\n' "$(date -u +%s)"
  printf 'backup_set_file=%s\n' "$manifest_name"
  printf 'postgres_file=%s\n' "$postgres_name"
  printf 'postgres_size=%s\n' "$postgres_size"
  printf 'minio_file=%s\n' "$minio_name"
  printf 'minio_size=%s\n' "$minio_size"
  printf 'remote_bucket=%s\n' "$bucket"
  printf 'remote_prefix=%s\n' "$prefix"
} > "$temporary_status"
chmod 600 "$temporary_status"
mv -f "$temporary_status" "$STATUS_FILE"
printf 'off-site backup set replicated: set=%s postgres=%s minio=%s\n' "$manifest_name" "$postgres_name" "$minio_name"
