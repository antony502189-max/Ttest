#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/srv/112233.es}"
ENV_FILE="$ROOT/shared/production.env"
COMPOSE_FILE="$ROOT/current/docker-compose.production.yml"
domain="$(grep '^APP_DOMAIN=' "$ENV_FILE" | cut -d= -f2-)"
[[ -n "$domain" ]] || { echo "APP_DOMAIN is missing from $ENV_FILE" >&2; exit 65; }
compose=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")
"${compose[@]}" ps
"${compose[@]}" exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live', timeout=3); urllib.request.urlopen('http://localhost:8000/health/ready', timeout=3)"
"${compose[@]}" exec -T postgres psql -U "$(grep '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2-)" -d "$(grep '^POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2-)" -tAc 'SELECT PostGIS_Version();'
"${compose[@]}" exec -T redis redis-cli ping

# The frontend starts after the backend health gate; give Traefik and Nginx a
# bounded window to publish the configured public origin. The verifier checks
# an application fingerprint plus exact health/catalog/admin status codes.
for _ in $(seq 1 30); do
  if APP_DOMAIN="$domain" "$ROOT/current/deploy/verify-public-origin.sh" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
APP_DOMAIN="$domain" "$ROOT/current/deploy/verify-public-origin.sh"
curl --fail --silent --show-error "https://$domain/privacidad" >/dev/null
curl --fail --silent --show-error "https://$domain/terminos" >/dev/null

# Interactive API metadata is useful in development, but must not be exposed
# from the public production origin.
for path in /api/docs /api/openapi.json; do
  status="$(curl --silent --output /dev/null --write-out '%{http_code}' "https://$domain$path")"
  [[ "$status" == "404" ]] || { echo "expected $path to return 404, got $status" >&2; exit 65; }
done
