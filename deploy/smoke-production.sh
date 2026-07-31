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
curl --fail --silent --show-error --location "https://$domain/" >/dev/null
curl --fail --silent --show-error "https://$domain/api/openapi.json" >/dev/null
