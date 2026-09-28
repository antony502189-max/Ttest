#!/usr/bin/env bash
set -euo pipefail
umask 077

# Dry run by default. --apply requires two newer, authenticated archives of
# each type before any older archive of that type can be removed.
ROOT="${ROOT:-/srv/112233.es}"
ENV_FILE="${ENV_FILE:-$ROOT/shared/production.env}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
mode="${1:---dry-run}"
[[ "$mode" == "--dry-run" || "$mode" == "--apply" ]] || { echo "usage: $0 [--dry-run|--apply]" >&2; exit 64; }
[[ "$RETENTION_DAYS" =~ ^[1-9][0-9]*$ ]] || { echo "BACKUP_RETENTION_DAYS must be positive" >&2; exit 64; }
command -v flock >/dev/null || { echo "flock is required" >&2; exit 69; }
LOCK_FILE="$ROOT/shared/release.lock"
exec 9>"$LOCK_FILE"
flock -n 9 || { echo "release or backup operation is running" >&2; exit 75; }
# shellcheck source=deploy/backup-crypto.sh
source "$SCRIPT_DIR/backup-crypto.sh"
load_backup_keys "$ENV_FILE"
now="$(date +%s)"
shopt -s nullglob

for kind in postgres minio; do
  archives=("$BACKUP_DIR"/"$kind"-*.enc)
  first=""; second=""; first_time=0; second_time=0
  for archive in "${archives[@]}"; do
    [[ -s "$archive" ]] || continue
    modified="$(stat -c %Y "$archive")"
    if (( modified > first_time )); then
      second="$first"; second_time="$first_time"
      first="$archive"; first_time="$modified"
    elif (( modified > second_time )); then
      second="$archive"; second_time="$modified"
    fi
  done
  if [[ -z "$first" || -z "$second" ]] || ! verify_backup_authentication "$first" || ! verify_backup_authentication "$second"; then
    echo "$kind: fewer than two newer authenticated archives; retaining all" >&2
    continue
  fi
  for archive in "${archives[@]}"; do
    [[ "$archive" == "$first" || "$archive" == "$second" ]] && continue
    modified="$(stat -c %Y "$archive")"
    (( modified < second_time && now - modified > RETENTION_DAYS * 86400 )) || continue
    if [[ "$mode" == "--apply" ]]; then
      rm -f -- "$archive" "${archive}.hmac"
      printf 'deleted %s\n' "$archive"
    else
      printf 'would delete %s\n' "$archive"
    fi
  done
done
