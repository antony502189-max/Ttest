#!/usr/bin/env bash
# Shared helpers for encrypted backup creation and verification.
# This file is sourced by the backup/restore scripts and must not be executed.

load_backup_keys() {
  local env_file="$1"
  [[ -r "$env_file" ]] || { echo "missing $env_file" >&2; return 65; }
  [[ "$(stat -c %a "$env_file")" == "600" ]] || {
    echo "$env_file must have mode 600" >&2
    return 65
  }

  # Preserve dotenv values after the first '=' verbatim. Production secrets in
  # this file are intentionally unquoted single-line values.
  BACKUP_ENCRYPTION_KEY="$(sed -n 's/^BACKUP_ENCRYPTION_KEY=//p' "$env_file" | tail -n 1)"
  BACKUP_AUTHENTICATION_KEY="$(sed -n 's/^BACKUP_AUTHENTICATION_KEY=//p' "$env_file" | tail -n 1)"
  export BACKUP_ENCRYPTION_KEY BACKUP_AUTHENTICATION_KEY

  [[ ${#BACKUP_ENCRYPTION_KEY} -ge 32 ]] || {
    echo "BACKUP_ENCRYPTION_KEY must contain at least 32 characters" >&2
    return 65
  }
  [[ ${#BACKUP_AUTHENTICATION_KEY} -ge 32 ]] || {
    echo "BACKUP_AUTHENTICATION_KEY must contain at least 32 characters" >&2
    return 65
  }
  [[ "$BACKUP_ENCRYPTION_KEY" != "$BACKUP_AUTHENTICATION_KEY" ]] || {
    echo "backup encryption and authentication keys must be independent" >&2
    return 65
  }
  command -v python3 >/dev/null 2>&1 || {
    echo "python3 is required for authenticated backup operations" >&2
    return 65
  }
}

write_backup_hmac() {
  local encrypted_file="$1"
  local temporary_mac
  temporary_mac="$(mktemp "${encrypted_file}.hmac.tmp.XXXXXX")"
  if ! python3 - "$encrypted_file" "$temporary_mac" <<'PY'
import hashlib
import hmac
import os
import sys

source, destination = sys.argv[1:3]
mac = hmac.new(os.environ["BACKUP_AUTHENTICATION_KEY"].encode(), digestmod=hashlib.sha256)
with open(source, "rb") as stream:
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        mac.update(chunk)
with open(destination, "wb") as output:
    output.write(mac.digest())
PY
  then
    rm -f "$temporary_mac"
    return 1
  fi
  chmod 600 "$temporary_mac"
  mv -f "$temporary_mac" "${encrypted_file}.hmac"
}

verify_backup_authentication() {
  local encrypted_file="$1"
  local stored_mac="${encrypted_file}.hmac"

  if [[ ! -f "$stored_mac" ]]; then
    if [[ "${ALLOW_LEGACY_UNAUTHENTICATED_BACKUP:-0}" == "1" && -f "${encrypted_file}.sha256" ]]; then
      echo "warning: verifying legacy backup without cryptographic authentication" >&2
      sha256sum -c "${encrypted_file}.sha256"
      return
    fi
    echo "missing authenticated backup MAC: $stored_mac" >&2
    echo "set ALLOW_LEGACY_UNAUTHENTICATED_BACKUP=1 only for a trusted pre-MAC backup" >&2
    return 65
  fi

  if ! python3 - "$encrypted_file" "$stored_mac" <<'PY'
import hashlib
import hmac
import os
import sys

source, stored_path = sys.argv[1:3]
mac = hmac.new(os.environ["BACKUP_AUTHENTICATION_KEY"].encode(), digestmod=hashlib.sha256)
with open(source, "rb") as stream:
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        mac.update(chunk)
with open(stored_path, "rb") as stored:
    expected = stored.read()
if len(expected) != hashlib.sha256().digest_size or not hmac.compare_digest(expected, mac.digest()):
    raise SystemExit(1)
PY
  then
    echo "backup authentication failed: $encrypted_file" >&2
    return 65
  fi
}

# Optional machine-verifiable receipt, written only after the restore drill succeeds.
write_recovery_receipt() {
  local kind="$1" backup="$2"
  [[ -n "${RECOVERY_RECEIPT:-}" ]] || return 0
  python3 - "$kind" "$backup" "$RECOVERY_RECEIPT" "$ROOT" <<'PY'
import hashlib, json, os, pathlib, sys
from datetime import datetime, timezone
kind, backup_name, output_name, root_name = sys.argv[1:]
root = pathlib.Path(root_name).resolve()
backup = pathlib.Path(backup_name).resolve(strict=True)
output = pathlib.Path(output_name)
if backup.parent != root / "backups" or output.parent.resolve() != root / "shared" / "rental-policy":
    raise SystemExit("Recovery receipt and backup must use the private production directories")
output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
os.chmod(output.parent, 0o700)
h = hashlib.sha256()
with backup.open("rb") as stream:
    for chunk in iter(lambda: stream.read(1024*1024), b""):
        h.update(chunk)
value = dict(kind=kind, backup=str(backup), sha256=h.hexdigest(), restored=True,
             verified_at=datetime.now(timezone.utc).isoformat())
# Never overwrite a proof, follow a symlink, or reuse a failed drill's receipt.
with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
    json.dump(value, stream, sort_keys=True)
    stream.write("\n")
PY
  write_backup_hmac "$RECOVERY_RECEIPT"
}
