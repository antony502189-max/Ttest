#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT

cat > "$temp_dir/curl" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
out=""
url=""
while (($#)); do
  case "$1" in
    --output) out="$2"; shift 2 ;;
    --write-out) shift 2 ;;
    --silent|--show-error|--location) shift ;;
    --max-time) shift 2 ;;
    *) url="$1"; shift ;;
  esac
done
case "${SMOKE_SCENARIO:-ok}:$url" in
  wrong-origin:*) printf '%s' '<html><title>Other application</title></html>' > "$out"; printf '200' ;;
  ok:https://example.test/) printf '%s' '<html><script src="/assets/app.js"></script><div id="root"></div></html>' > "$out"; printf '200' ;;
  ok:https://example.test/api/health/live|ok:https://example.test/api/health/ready) printf '%s' '{"status":"ok"}' > "$out"; printf '200' ;;
  ok:https://example.test/api/v1/listings/catalog-version) printf '%s' '{"version":"1"}' > "$out"; printf '200' ;;
  ok:https://example.test/api/v1/admin/access) printf '%s' '{"detail":"Authentication required"}' > "$out"; printf '401' ;;
  *) printf '%s' '{}' > "$out"; printf '404' ;;
esac
EOF
chmod 700 "$temp_dir/curl"

APP_DOMAIN=example.test CURL_BIN="$temp_dir/curl" "$root/deploy/verify-public-origin.sh"
if APP_DOMAIN=example.test CURL_BIN="$temp_dir/curl" SMOKE_SCENARIO=wrong-origin "$root/deploy/verify-public-origin.sh"; then
  echo "wrong public origin unexpectedly passed release acceptance" >&2
  exit 1
fi
echo "public-origin acceptance rejects an unrelated healthy-looking 200 page"
