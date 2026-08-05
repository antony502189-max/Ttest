#!/usr/bin/env bash
set -euo pipefail
umask 077

# Run on the VPS. The object stream is encrypted before it reaches the host;
# this script never removes buckets, objects, volumes, or prior backups.
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
archive="$BACKUP_DIR/minio-$stamp.tar.enc"
temporary_archive="$(mktemp "$BACKUP_DIR/.minio-$stamp.XXXXXX.tmp")"
compose=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")
cleanup() { rm -f "$temporary_archive"; }
trap cleanup EXIT

"${compose[@]}" run --rm -T --entrypoint /bin/sh minio-init -ec '
  ready=0
  attempt=0
  while [ "$attempt" -lt 60 ]; do
    if mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null 2>&1; then
      ready=1
      break
    fi
    attempt=$((attempt + 1))
    sleep 2
  done
  [ "$ready" -eq 1 ] || { echo "MinIO did not become ready for backup" >&2; exit 65; }
  busybox mkdir -p /tmp/minio-backup
  mc mirror --overwrite "local/$S3_BUCKET" /tmp/minio-backup >/dev/null
  (
    cd /tmp/minio-backup
    # Build the manifest outside the mirrored tree so it can never include or
    # checksum itself. Copy it into the archive only after enumeration ends.
    busybox find . -type f -print | LC_ALL=C busybox sort | while IFS= read -r object; do
      busybox sha256sum "$object"
    done > /tmp/backup-manifest
    busybox cp /tmp/backup-manifest .backup-manifest
  )
  busybox tar -C /tmp/minio-backup -cf - .
' | openssl enc -aes-256-cbc -pbkdf2 -salt \
      -pass env:BACKUP_ENCRYPTION_KEY -out "$temporary_archive"

[[ -s "$temporary_archive" ]] || { echo "MinIO backup is empty" >&2; exit 65; }
chmod 600 "$temporary_archive"
mv "$temporary_archive" "$archive"
write_backup_hmac "$archive"
trap - EXIT
printf '%s\n' "$archive"
