#!/usr/bin/env bash
set -euo pipefail
umask 077
# Operator-only apply; never called by deployment/startup. Does not stop/restart services.
[[ $# -eq 4 ]] || { echo "usage: $0 MANIFEST CONFIRMATION POSTGRES_RECEIPT MINIO_RECEIPT" >&2; exit 64; }
ROOT="${ROOT:-/srv/112233.es}"
ENV_FILE="${ENV_FILE:-$ROOT/shared/production.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/current/docker-compose.production.yml}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
command -v flock >/dev/null
exec 9>"$ROOT/shared/release.lock"
chmod 600 "$ROOT/shared/release.lock"
flock -n 9 || { echo "production maintenance lock is busy" >&2; exit 75; }
source "$SCRIPT_DIR/backup-crypto.sh"
load_backup_keys "$ENV_FILE"
# Explicit approval must come from the operator for these exact manifest bytes.
manifest="$(realpath -e -- "$1")"
postgres_receipt="$(realpath -e -- "$3")"
minio_receipt="$(realpath -e -- "$4")"
for artifact in "$manifest" "$postgres_receipt" "$minio_receipt"; do
  [[ "$(dirname -- "$artifact")" == "$ROOT/shared/rental-policy" ]] || { echo "artifacts must use the private rental-policy directory" >&2; exit 65; }
  [[ "$(stat -c %a "$artifact")" == "600" ]] || { echo "artifact must have mode 600" >&2; exit 65; }
done
verify_backup_authentication "$postgres_receipt"
verify_backup_authentication "$minio_receipt"
# Verify MACs on the exact backup paths referenced by authenticated receipts.
for receipt in "$postgres_receipt" "$minio_receipt"; do
  backup="$(python3 - "$receipt" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["backup"])
PY
)"
  [[ "$(dirname -- "$(realpath -e -- "$backup")")" == "$ROOT/backups" ]] || exit 65
  verify_backup_authentication "$backup"
done
compose=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")
# Abort if ANY compose service except infrastructure is running. This catches
# renamed workers/new writers instead of relying on an incomplete service list.
running="$("${compose[@]}" ps --status running --services)"
while IFS= read -r service; do
  case "$service" in postgres|redis|minio|"") ;; *) echo "stop all application writers before apply: $service" >&2; exit 65 ;; esac
done <<< "$running"
result="$ROOT/shared/rental-policy/apply-$(date -u +%Y%m%dT%H%M%SZ)-$$.json"
# Mount identical absolute paths so backup hashes in the authenticated receipts
# can be checked again inside the application transaction.
"${compose[@]}" run --rm -T --no-deps --user "$(id -u):$(id -g)" \
  -e RENTAL_POLICY_RELEASE_LOCK_HELD=1 -e BACKUP_AUTHENTICATION_KEY \
  -v "$ROOT/backups:$ROOT/backups:ro" -v "$ROOT/shared/rental-policy:$ROOT/shared/rental-policy" \
  backend python -m app.commands.enforce_long_term_price_policy --apply \
  --manifest "$manifest" --confirm "$2" --recovery-receipt "$postgres_receipt" \
  --recovery-receipt "$minio_receipt" --output "$result"
