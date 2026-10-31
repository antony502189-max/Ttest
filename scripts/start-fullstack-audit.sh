#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Both PR and post-merge audits use the same explicitly test-only geocoder.
# Never add this override to the production image or production Compose.
compose=(docker compose -f docker-compose.yml -f docker-compose.fullstack-test.yml)
"${compose[@]}" up -d postgres redis minio minio-init mailpit migrate backend mail-worker
"${compose[@]}" --profile tools run --rm seed

for attempt in {1..60}; do
  if curl --fail --silent http://127.0.0.1:8000/health/ready >/dev/null; then
    break
  fi
  if [[ "$attempt" == 60 ]]; then
    echo 'Isolated full-stack backend did not become ready' >&2
    exit 1
  fi
  sleep 2
done
curl --fail --silent http://127.0.0.1:8000/metrics >/dev/null
