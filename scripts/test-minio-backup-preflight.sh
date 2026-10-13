#!/usr/bin/env bash
set -euo pipefail

# This test uses synthetic encrypted-file bytes with authentic HMACs. It does
# not connect to a server, restore objects, or alter a production backup.
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
preflight="$repo_root/deploy/require-fresh-minio-backup.sh"
fixture_root="$(mktemp -d)"
trap 'rm -rf "$fixture_root"' EXIT
mkdir -p "$fixture_root/shared" "$fixture_root/backups"
export ENV_FILE="$fixture_root/shared/production.env"
export BACKUP_DIR="$fixture_root/backups"
export MINIO_BACKUP_MAX_AGE_HOURS=1
cat > "$ENV_FILE" <<'EOF'
BACKUP_ENCRYPTION_KEY=synthetic-encryption-key-not-for-production-12345
BACKUP_AUTHENTICATION_KEY=synthetic-authentication-key-not-for-production-56789
EOF
chmod 600 "$ENV_FILE"
source "$repo_root/deploy/backup-crypto.sh"
load_backup_keys "$ENV_FILE"

archive="$BACKUP_DIR/minio-20261013-120000.tar.enc"
printf '%s' 'synthetic encrypted fixture' > "$archive"
write_backup_hmac "$archive"

expect_refusal() {
  if "$@" > "$fixture_root/output" 2> "$fixture_root/error"; then
    echo "MinIO release preflight incorrectly accepted an invalid backup" >&2
    exit 1
  fi
}

[[ "$(bash "$preflight")" == "$archive" ]] || { echo 'fresh authenticated archive was rejected' >&2; exit 1; }
touch -d '3 hours ago' "$archive"
expect_refusal bash "$preflight"

touch "$archive"
printf '%s' 'tampering' >> "$archive"
expect_refusal bash "$preflight"

printf '%s' 'synthetic encrypted fixture' > "$archive"
write_backup_hmac "$archive"
touch -d '+30 minutes' "$archive"
expect_refusal bash "$preflight"

touch "$archive"
[[ "$(bash "$preflight")" == "$archive" ]] || { echo 'restored authenticated archive was rejected' >&2; exit 1; }
rm -f "$archive.hmac"
sha256sum "$archive" > "$archive.sha256"
expect_refusal env ALLOW_LEGACY_UNAUTHENTICATED_BACKUP=1 bash "$preflight"

echo 'MinIO release preflight rejects stale, tampered, future-dated and legacy unauthenticated backups'
