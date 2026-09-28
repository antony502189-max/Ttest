#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT="${ROOT:-/srv/112233.es}"
ENV_FILE="${ENV_FILE:-$ROOT/shared/production.env}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
MAX_AGE_HOURS="${MINIO_BACKUP_MAX_AGE_HOURS:-72}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
[[ "$MAX_AGE_HOURS" =~ ^[1-9][0-9]*$ ]] || { echo "MINIO_BACKUP_MAX_AGE_HOURS must be positive" >&2; exit 64; }
# shellcheck source=deploy/backup-crypto.sh
source "$SCRIPT_DIR/backup-crypto.sh"
load_backup_keys "$ENV_FILE"

now="$(date +%s)"
shopt -s nullglob
for archive in "$BACKUP_DIR"/minio-*.tar.enc; do
  [[ -s "$archive" ]] || continue
  modified="$(stat -c %Y "$archive")"
  (( now - modified <= MAX_AGE_HOURS * 3600 )) || continue
  if verify_backup_authentication "$archive"; then
    printf '%s\n' "$archive"
    exit 0
  fi
done
echo "No authenticated MinIO backup is fresh enough. Run deploy/backup-minio.sh as a separate scheduled or manual job before deploying." >&2
exit 65
