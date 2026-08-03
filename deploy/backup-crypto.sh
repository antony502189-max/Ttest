#!/usr/bin/env bash
# Shared helpers for encrypted backup creation and verification.
# This file is sourced by the backup/restore scripts and must not be executed.

load_backup_keys() {
  local env_file="$1"
  [[ -r "$env_file" ]] || { echo "missing $env_file" >&2; return 65; }

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
}

write_backup_hmac() {
  local encrypted_file="$1"
  local temporary_mac
  temporary_mac="$(mktemp "${encrypted_file}.hmac.tmp.XXXXXX")"
  if ! openssl dgst -sha256 -mac HMAC \
    -macopt keyenv:BACKUP_AUTHENTICATION_KEY \
    -binary "$encrypted_file" > "$temporary_mac"; then
    rm -f "$temporary_mac"
    return 1
  fi
  chmod 600 "$temporary_mac"
  mv -f "$temporary_mac" "${encrypted_file}.hmac"
}

verify_backup_authentication() {
  local encrypted_file="$1"
  local stored_mac="${encrypted_file}.hmac"
  local calculated_mac

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

  calculated_mac="$(mktemp "${encrypted_file}.verify.tmp.XXXXXX")"
  if ! openssl dgst -sha256 -mac HMAC \
    -macopt keyenv:BACKUP_AUTHENTICATION_KEY \
    -binary "$encrypted_file" > "$calculated_mac"; then
    rm -f "$calculated_mac"
    return 1
  fi
  if ! cmp -s "$stored_mac" "$calculated_mac"; then
    rm -f "$calculated_mac"
    echo "backup authentication failed: $encrypted_file" >&2
    return 65
  fi
  rm -f "$calculated_mac"
}
