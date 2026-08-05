#!/usr/bin/env bash
set -euo pipefail
umask 077

# Restore only into a unique temporary bucket and remove that bucket on exit.
[[ $# -eq 1 ]] || { echo "usage: $0 /absolute/path/to/minio-backup.tar.enc" >&2; exit 64; }
ROOT="${ROOT:-/srv/112233.es}"
ENV_FILE="${ENV_FILE:-$ROOT/shared/production.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/current/docker-compose.production.yml}"
ARCHIVE="$1"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
command -v flock >/dev/null || { echo "flock is required for production restore serialization" >&2; exit 69; }
exec 9>"$ROOT/shared/release.lock"
chmod 600 "$ROOT/shared/release.lock"
flock -n 9 || { echo "a production deploy, rollback, backup, or restore drill is already running" >&2; exit 75; }
# shellcheck source=deploy/backup-crypto.sh
source "$SCRIPT_DIR/backup-crypto.sh"

[[ -f "$ARCHIVE" && "$ARCHIVE" == "$ROOT/backups/"*.tar.enc ]] || {
  echo "encrypted backup must be under $ROOT/backups" >&2
  exit 65
}
load_backup_keys "$ENV_FILE"
verify_backup_authentication "$ARCHIVE"

bucket="restore-verify-$(date -u +%s)-$$-$RANDOM"
compose=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

cleanup() {
  "${compose[@]}" run --rm -T -e "RESTORE_VERIFY_BUCKET=$bucket" --entrypoint /bin/sh minio-init -ec '
    mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null
    mc rb --force "local/$RESTORE_VERIFY_BUCKET" || true
  ' >/dev/null 2>&1 || true
}
trap cleanup EXIT

openssl enc -d -aes-256-cbc -pbkdf2 -pass env:BACKUP_ENCRYPTION_KEY -in "$ARCHIVE" \
  | "${compose[@]}" run --rm -T -e "RESTORE_VERIFY_BUCKET=$bucket" --entrypoint /bin/sh minio-init -ec '
      mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null
      busybox mkdir -p /tmp/minio-restore
      busybox tar -C /tmp/minio-restore -xf -
      test -f /tmp/minio-restore/.backup-manifest
      expected="$(busybox wc -l < /tmp/minio-restore/.backup-manifest)"
      busybox cp /tmp/minio-restore/.backup-manifest /tmp/backup-manifest
      busybox rm -f /tmp/minio-restore/.backup-manifest
      mc mb "local/$RESTORE_VERIFY_BUCKET" >/dev/null
      mc mirror --overwrite /tmp/minio-restore "local/$RESTORE_VERIFY_BUCKET" >/dev/null
      busybox mkdir -p /tmp/minio-restored
      mc mirror --overwrite "local/$RESTORE_VERIFY_BUCKET" /tmp/minio-restored >/dev/null
      actual="$(busybox find /tmp/minio-restored -type f | busybox wc -l)"
      test "$actual" -eq "$expected"
      if [ "$expected" -gt 0 ]; then
        (cd /tmp/minio-restored && busybox sha256sum -c /tmp/backup-manifest >/dev/null)
      fi
      printf "verified_objects=%s\n" "$actual"
    '
