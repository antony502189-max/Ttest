#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/srv/112233.es}"
ENV_FILE="$ROOT/shared/production.env"
COMPOSE_FILE="$ROOT/current/docker-compose.production.yml"
domain="$(grep '^APP_DOMAIN=' "$ENV_FILE" | cut -d= -f2-)"
compose=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")
"${compose[@]}" ps
"${compose[@]}" exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live', timeout=3); urllib.request.urlopen('http://localhost:8000/health/ready', timeout=3)"
"${compose[@]}" exec -T postgres psql -U "$(grep '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2-)" -d "$(grep '^POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2-)" -tAc 'SELECT PostGIS_Version();'
"${compose[@]}" exec -T redis redis-cli ping

# The frontend starts after the backend health gate; give Traefik and Nginx a
# bounded window to publish the new container before asserting public routes.
for _ in $(seq 1 30); do
  if curl --fail --silent --show-error --location "https://$domain/" >/dev/null; then
    break
  fi
  sleep 2
done
curl --fail --silent --show-error --location "https://$domain/" >/dev/null
curl --fail --silent --show-error "https://$domain/api/health/live" >/dev/null
curl --fail --silent --show-error "https://$domain/api/health/ready" >/dev/null
curl --fail --silent --show-error "https://$domain/api/v1/listings" >/dev/null
curl --fail --silent --show-error "https://$domain/privacidad" >/dev/null
curl --fail --silent --show-error "https://$domain/terminos" >/dev/null

# Interactive API metadata is useful in development, but must not be exposed
# from the public production origin.
for path in /api/docs /api/openapi.json; do
  status="$(curl --silent --output /dev/null --write-out '%{http_code}' "https://$domain$path")"
  [[ "$status" == "404" ]] || { echo "expected $path to return 404, got $status" >&2; exit 65; }
done
