#!/usr/bin/env bash
set -euo pipefail

# Run on the VPS. The object stream is encrypted before it reaches the host;
# this script never removes buckets, objects, volumes, or prior backups.
ROOT="${ROOT:-/srv/112233.es}"
ENV_FILE="${ENV_FILE:-$ROOT/shared/production.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/current/docker-compose.production.yml}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
[[ -r "$ENV_FILE" ]] || { echo "missing $ENV_FILE" >&2; exit 65; }
# Preserve the dotenv value after the first '=' verbatim; secrets may contain '='.
BACKUP_ENCRYPTION_KEY="$(sed -n 's/^BACKUP_ENCRYPTION_KEY=//p' "$ENV_FILE" | tail -n 1)"
export BACKUP_ENCRYPTION_KEY
[[ -n "$BACKUP_ENCRYPTION_KEY" ]] || { echo "BACKUP_ENCRYPTION_KEY is required" >&2; exit 65; }
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

stamp="$(date -u +%Y%m%d-%H%M%S)"
archive="$BACKUP_DIR/minio-$stamp.tar.enc"
checksum="$archive.sha256"
compose=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

"${compose[@]}" run --rm -T --entrypoint /bin/sh minio-init -ec '
  mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
  mkdir -p /tmp/minio-backup
  mc mirror --overwrite "local/$S3_BUCKET" /tmp/minio-backup
  mc find "local/$S3_BUCKET" | wc -l > /tmp/minio-backup/.backup-object-count
  tar -C /tmp/minio-backup -cf - .
' | openssl enc -aes-256-cbc -pbkdf2 -salt -pass env:BACKUP_ENCRYPTION_KEY -out "$archive"
sha256sum "$archive" > "$checksum"
chmod 600 "$archive" "$checksum"
printf '%s\n' "$archive"
