#!/usr/bin/env bash
set -euo pipefail

# Verify the externally routable application, not merely container readiness.
# APP_DOMAIN is deliberately the sole origin input: the apex may be owned by a
# different service while the application runs on a configured subdomain.
domain="${APP_DOMAIN:?APP_DOMAIN is required}"
curl_bin="${CURL_BIN:-curl}"
origin="https://$domain"
timeout_seconds="${PUBLIC_SMOKE_TIMEOUT_SECONDS:-20}"
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

request() {
  local path="$1" expected_status="$2" body="$work_dir/body"
  local actual_status
  actual_status="$("$curl_bin" --silent --show-error --location --max-time "$timeout_seconds" \
    --output "$body" --write-out '%{http_code}' "$origin$path")" || {
      echo "public origin request failed: $origin$path" >&2
      return 1
    }
  [[ "$actual_status" == "$expected_status" ]] || {
    echo "expected $origin$path to return $expected_status, got $actual_status" >&2
    return 1
  }
}

request / 200
# An unrelated 200 page must not satisfy release acceptance. These are stable
# application-shell characteristics, complemented by API response assertions.
grep -Fq '<div id="root"' "$work_dir/body" || {
  echo "public origin did not return the expected application shell" >&2
  exit 65
}
grep -Fq '/assets/' "$work_dir/body" || {
  echo "public origin did not return application assets" >&2
  exit 65
}

request /api/health/live 200
grep -Fq '"status":"ok"' "$work_dir/body" || {
  echo "live endpoint did not return the expected application health payload" >&2
  exit 65
}

request /api/health/ready 200
grep -Fq '"status":"ok"' "$work_dir/body" || {
  echo "ready endpoint did not return the expected application health payload" >&2
  exit 65
}

request /api/v1/listings/catalog-version 200
grep -Fq '"version"' "$work_dir/body" || {
  echo "catalog endpoint did not return the expected application payload" >&2
  exit 65
}

request /api/v1/admin/access 401
grep -Fq 'Authentication required' "$work_dir/body" || {
  echo "anonymous admin endpoint did not return the expected authentication rejection" >&2
  exit 65
}

printf 'public origin verified: %s\n' "$origin"
