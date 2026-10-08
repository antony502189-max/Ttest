#!/usr/bin/env bash
set -euo pipefail

image='nginxinc/nginx-unprivileged:1.27-alpine@sha256:65e3e85dbaed8ba248841d9d58a899b6197106c23cb0ff1a132b7bfe0547e4c0'
tmp_dir="$(mktemp -d)"
container_id=''

cleanup() {
  if [[ -n "$container_id" ]]; then
    docker rm -f "$container_id" >/dev/null 2>&1 || true
  fi
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

mkdir -p "$tmp_dir/root/assets"
cat > "$tmp_dir/backend.conf" <<'NGINX'
server {
  listen 8000;
  default_type application/json;
  location / {
    root /usr/share/nginx/html;
    try_files /api.json =404;
  }
}
NGINX
{
  printf '<!doctype html><title>fixture</title>'
  head -c 4096 /dev/zero | tr '\0' x
} > "$tmp_dir/root/index.html"
printf '%s\n' '<svg xmlns="http://www.w3.org/2000/svg"><title>icon</title></svg>' > "$tmp_dir/root/favicon.svg"
printf '%s\n' '<svg xmlns="http://www.w3.org/2000/svg"><title>logo</title></svg>' > "$tmp_dir/root/logo.svg"
{
  printf '{"commit":"fixture","padding":"'
  head -c 4096 /dev/zero | tr '\0' x
  printf '"}'
} > "$tmp_dir/root/build-info.json"
{
  printf '{"type":"FeatureCollection","padding":"'
  head -c 4096 /dev/zero | tr '\0' x
  printf '"}'
} > "$tmp_dir/root/assets/zone-01234567.geojson"
cp "$tmp_dir/root/assets/zone-01234567.geojson" "$tmp_dir/root/zone.geojson"
printf '%s\n' 'const stable = true;' > "$tmp_dir/root/assets/stable.js"
{
  printf '{"data":"'
  head -c 4096 /dev/zero | tr '\0' x
  printf '"}'
} > "$tmp_dir/root/api.json"
{
  printf 'const fixture = "'
  head -c 4096 /dev/zero | tr '\0' x
  printf '";'
} > "$tmp_dir/root/assets/app-01234567.js"
{
  printf '/* fixture */'
  for _ in $(seq 1 200); do printf '.class { color: #123; }'; done
} > "$tmp_dir/root/assets/app-01234567.css"

container_id="$(docker run -d --rm \
  --add-host backend:127.0.0.1 \
  -p 127.0.0.1:18083:8080 \
  --mount "type=bind,src=$PWD/deploy/nginx.conf,dst=/etc/nginx/conf.d/default.conf,readonly" \
  --mount "type=bind,src=$tmp_dir/backend.conf,dst=/etc/nginx/conf.d/upstream-test.conf,readonly" \
  --mount "type=bind,src=$tmp_dir/root,dst=/usr/share/nginx/html,readonly" \
  "$image")"
base_url='http://127.0.0.1:18083'

ready=0
for _ in $(seq 1 30); do
  if curl --silent --show-error --fail "$base_url/" -o /dev/null 2>/dev/null; then
    ready=1
    break
  fi
  sleep 1
done
test "$ready" = 1

assert_header() {
  local headers="$1" name="$2" value="$3"
  grep -Eiq "^${name}:[[:space:]]*${value}[[:space:]]*\$" "$headers" || {
    echo "expected $name: $value in $headers" >&2
    cat "$headers" >&2
    exit 1
  }
}

request() {
  local name="$1" path="$2" encoding="$3"
  shift 3
  curl --silent --show-error --dump-header "$tmp_dir/$name.headers" \
    --output "$tmp_dir/$name.body" "$@" \
    -H "Accept-Encoding: $encoding" "$base_url$path"
}

request html-identity / identity
test "$(wc -c < "$tmp_dir/html-identity.body")" -gt 1024
if grep -Eiq '^Content-Encoding:' "$tmp_dir/html-identity.headers"; then
  echo 'identity request unexpectedly received content encoding' >&2
  exit 1
fi
assert_header "$tmp_dir/html-identity.headers" 'Vary' '.*Accept-Encoding.*'
assert_header "$tmp_dir/html-identity.headers" 'Cache-Control' 'no-cache, must-revalidate'
assert_header "$tmp_dir/html-identity.headers" 'Content-Type' 'text/html'
assert_header "$tmp_dir/html-identity.headers" 'X-Frame-Options' 'DENY'
assert_header "$tmp_dir/html-identity.headers" 'X-Content-Type-Options' 'nosniff'
identity_bytes="$(wc -c < "$tmp_dir/html-identity.body" | tr -d ' ')"
assert_header "$tmp_dir/html-identity.headers" 'Content-Length' "$identity_bytes"

curl --silent --show-error --dump-header "$tmp_dir/html-no-encoding.headers" \
  --output "$tmp_dir/html-no-encoding.body" "$base_url/"
if grep -Eiq '^Content-Encoding:' "$tmp_dir/html-no-encoding.headers"; then
  echo 'request without Accept-Encoding unexpectedly received compressed content' >&2
  exit 1
fi

request html-gzip / gzip
assert_header "$tmp_dir/html-gzip.headers" 'Content-Encoding' 'gzip'
assert_header "$tmp_dir/html-gzip.headers" 'Vary' '.*Accept-Encoding.*'
if grep -Eiq '^Content-Length:' "$tmp_dir/html-gzip.headers"; then
  echo 'compressed response unexpectedly retained the identity Content-Length' >&2
  exit 1
fi
gzip -dc "$tmp_dir/html-gzip.body" > "$tmp_dir/html-decoded.body"
cmp "$tmp_dir/html-identity.body" "$tmp_dir/html-decoded.body"
test "$(wc -c < "$tmp_dir/html-gzip.body")" -lt "$(wc -c < "$tmp_dir/html-identity.body")"

request js-gzip /assets/app-01234567.js gzip
assert_header "$tmp_dir/js-gzip.headers" 'Content-Encoding' 'gzip'
assert_header "$tmp_dir/js-gzip.headers" 'Cache-Control' 'public, max-age=31536000, immutable'
gzip -dc "$tmp_dir/js-gzip.body" > "$tmp_dir/js-decoded.body"
grep -Fq 'const fixture' "$tmp_dir/js-decoded.body"

request css-gzip /assets/app-01234567.css gzip
assert_header "$tmp_dir/css-gzip.headers" 'Content-Encoding' 'gzip'
assert_header "$tmp_dir/css-gzip.headers" 'Content-Type' 'text/css'
assert_header "$tmp_dir/css-gzip.headers" 'Cache-Control' 'public, max-age=31536000, immutable'
gzip -dc "$tmp_dir/css-gzip.body" | grep -Fq '.class'

request geojson-gzip /assets/zone-01234567.geojson gzip
assert_header "$tmp_dir/geojson-gzip.headers" 'Content-Encoding' 'gzip'
assert_header "$tmp_dir/geojson-gzip.headers" 'Content-Type' 'application/geo\+json'
assert_header "$tmp_dir/geojson-gzip.headers" 'Cache-Control' 'public, max-age=31536000, immutable'
gzip -dc "$tmp_dir/geojson-gzip.body" | grep -Fq 'FeatureCollection'

request stable-js /assets/stable.js gzip
assert_header "$tmp_dir/stable-js.headers" 'Cache-Control' 'no-cache, must-revalidate'

request api-json /api/v1/test gzip
if grep -Eiq '^Content-Encoding:' "$tmp_dir/api-json.headers"; then
  echo 'proxied API JSON unexpectedly received compression' >&2
  exit 1
fi
assert_header "$tmp_dir/api-json.headers" 'Content-Type' 'application/json'
grep -Fq '"data"' "$tmp_dir/api-json.body"

request authorized-api /api/v1/test gzip -H 'Authorization: Bearer fixture-token'
if grep -Eiq '^Content-Encoding:' "$tmp_dir/authorized-api.headers"; then
  echo 'authenticated API response unexpectedly received compression' >&2
  exit 1
fi
request refresh-cookie-api /api/v1/test gzip -H 'Cookie: refresh_token=fixture-token'
if grep -Eiq '^Content-Encoding:' "$tmp_dir/refresh-cookie-api.headers"; then
  echo 'refresh-cookie API response unexpectedly received compression' >&2
  exit 1
fi
request auth-endpoint /api/v1/auth/login gzip
if grep -Eiq '^Content-Encoding:' "$tmp_dir/auth-endpoint.headers"; then
  echo 'token-issuing authentication response unexpectedly received compression' >&2
  exit 1
fi

request unsupported / br
if grep -Eiq '^Content-Encoding:' "$tmp_dir/unsupported.headers"; then
  echo 'unsupported encoding request unexpectedly received compressed content' >&2
  exit 1
fi

request stable-json /build-info.json gzip
assert_header "$tmp_dir/stable-json.headers" 'Cache-Control' 'no-cache, must-revalidate'
assert_header "$tmp_dir/stable-json.headers" 'Content-Type' 'application/json'
assert_header "$tmp_dir/stable-json.headers" 'Content-Encoding' 'gzip'
gzip -dc "$tmp_dir/stable-json.body" | grep -Fq '"commit":"fixture"'
request stable-svg /logo.svg gzip
assert_header "$tmp_dir/stable-svg.headers" 'Cache-Control' 'no-cache, must-revalidate'
request stable-geojson /zone.geojson gzip
assert_header "$tmp_dir/stable-geojson.headers" 'Cache-Control' 'no-cache, must-revalidate'
assert_header "$tmp_dir/stable-geojson.headers" 'Content-Type' 'application/geo\+json'
request favicon /favicon.svg gzip
assert_header "$tmp_dir/favicon.headers" 'Cache-Control' 'no-cache, must-revalidate'

etag="$(awk 'BEGIN { IGNORECASE = 1 } /^ETag:/ { sub(/^[^:]*:[[:space:]]*/, ""); gsub(/\r/, ""); print; exit }' "$tmp_dir/html-identity.headers")"
test -n "$etag"
request conditional / identity -H "If-None-Match: $etag"
grep -Eiq '^HTTP/[^ ]+ 304([[:space:]]|$)' "$tmp_dir/conditional.headers"
assert_header "$tmp_dir/conditional.headers" 'Cache-Control' 'no-cache, must-revalidate'

status="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
  -H 'Accept-Encoding: gzip' "$base_url/assets/missing-01234567.js")"
test "$status" = 404
curl --silent --show-error --dump-header "$tmp_dir/missing.headers" \
  --output /dev/null -H 'Accept-Encoding: gzip' \
  "$base_url/assets/missing-01234567.js"
if grep -Eiq '^Cache-Control:.*immutable' "$tmp_dir/missing.headers"; then
  echo 'missing build asset unexpectedly received an immutable cache header' >&2
  exit 1
fi

echo 'Nginx HTML/JS/CSS/static JSON compression, proxied API bypass, decoding, Vary, cache policy, 304, 404, and security header checks passed.'
