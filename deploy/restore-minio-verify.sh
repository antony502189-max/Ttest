#!/usr/bin/env bash
set -euo pipefail

# Restore only into a unique temporary bucket and remove that bucket on exit.
[[ $# -eq 1 ]] || { echo "usage: $0 /absolute/path/to/minio-backup.tar.enc" >&2; exit 64; }
ROOT="${ROOT:-/srv/112233.es}"
ENV_FILE="${ENV_FILE:-$ROOT/shared/production.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/current/docker-compose.production.yml}"
ARCHIVE="$1"
[[ -f "$ARCHIVE" && "$ARCHIVE" == "$ROOT/backups/"*.tar.enc ]] || { echo "encrypted backup must be under $ROOT/backups" >&2; exit 65; }
BACKUP_ENCRYPTION_KEY="$(grep '^BACKUP_ENCRYPTION_KEY=' "$ENV_FILE" | cut -d= -f2-)"
export BACKUP_ENCRYPTION_KEY
[[ -n "$BACKUP_ENCRYPTION_KEY" ]] || { echo "BACKUP_ENCRYPTION_KEY is required" >&2; exit 65; }
sha256sum -c "$ARCHIVE.sha256"
bucket="restore-verify-$(date -u +%s)"
compose=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

cleanup() {
  "${compose[@]}" run --rm -T -e "RESTORE_VERIFY_BUCKET=$bucket" --entrypoint /bin/sh minio-init -ec '
    mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
    mc rb --force "local/$RESTORE_VERIFY_BUCKET" || true
  ' >/dev/null 2>&1 || true
}
trap cleanup EXIT

openssl enc -d -aes-256-cbc -pbkdf2 -pass env:BACKUP_ENCRYPTION_KEY -in "$ARCHIVE" \
  | "${compose[@]}" run --rm -T -e "RESTORE_VERIFY_BUCKET=$bucket" --entrypoint /bin/sh minio-init -ec '
      mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
      mkdir -p /tmp/minio-restore
      tar -C /tmp/minio-restore -xf -
      expected="$(cat /tmp/minio-restore/.backup-object-count)"
      rm -f /tmp/minio-restore/.backup-object-count
      mc mb "local/$RESTORE_VERIFY_BUCKET"
      mc mirror --overwrite /tmp/minio-restore "local/$RESTORE_VERIFY_BUCKET"
      actual="$(mc find "local/$RESTORE_VERIFY_BUCKET" | wc -l)"
      test "$actual" -eq "$expected"
      printf "verified_objects=%s\n" "$actual"
    '
