#!/usr/bin/env bash
# A bounded, read-only production health check.  It deliberately does not run
# imports, backups, migrations, builds, or broad database queries.
set -euo pipefail
umask 077

ROOT="${ROOT:-/srv/112233.es}"
ENV_FILE="${ENV_FILE:-$ROOT/shared/production.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/current/docker-compose.production.yml}"
CHECK_TIMEOUT_SECONDS="${CHECK_TIMEOUT_SECONDS:-120}"

[[ -r "$ENV_FILE" ]] || { echo "missing production environment file" >&2; exit 65; }
[[ -f "$COMPOSE_FILE" ]] || { echo "missing production compose file" >&2; exit 65; }
command -v docker >/dev/null || { echo "docker is required" >&2; exit 69; }
command -v timeout >/dev/null || { echo "timeout is required" >&2; exit 69; }

# APP_DOMAIN is the only value read from the environment file and is not
# printed.  Do not source production.env: it contains credentials.
domain="$(sed -n 's/^APP_DOMAIN=//p' "$ENV_FILE" | tail -n 1)"
[[ "$domain" =~ ^[A-Za-z0-9.-]+$ ]] || { echo "invalid application domain" >&2; exit 65; }
compose=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

run() { timeout --foreground "$CHECK_TIMEOUT_SECONDS" "$@"; }

printf 'timestamp=%s\n' "$(date -u +%FT%TZ)"
printf 'release_sha=%s\n' "$(git -C "$ROOT/current" rev-parse --short=12 HEAD)"

for service in postgres redis minio backend mail-worker external-listings-worker frontend; do
  container="$("${compose[@]}" ps -q "$service")"
  [[ -n "$container" ]] || { echo "service_missing=$service" >&2; exit 1; }
  state="$(docker inspect --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' "$container")"
  [[ "$state" != exited* && "$state" != dead* && "$state" != created* && "$state" != *unhealthy* ]] || {
    echo "service_unhealthy=$service:$state" >&2
    exit 1
  }
  printf 'service_%s=%s\n' "$service" "$state"
done

run curl --fail --silent --show-error --max-time 5 --output /dev/null "https://$domain/"
run curl --fail --silent --show-error --max-time 5 --output /dev/null "https://$domain/api/health/live"
run curl --fail --silent --show-error --max-time 5 --output /dev/null "https://$domain/api/health/ready"
run "${compose[@]}" exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready', timeout=3)"
run "${compose[@]}" exec -T external-listings-worker python -m app.workers.external_listings --healthcheck
run "${compose[@]}" exec -T mail-worker python -m app.commands.outbox_worker --healthcheck

printf 'result=PASS\n'
