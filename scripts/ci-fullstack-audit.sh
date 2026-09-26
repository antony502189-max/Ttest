#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Backend lint, migrations, unit, PostgreSQL, and MinIO tests run in the
# independent Production audit job. This job exercises the real HTTP stack.
docker compose up -d postgres redis minio minio-init mailpit migrate backend mail-worker
docker compose --profile tools run --rm seed

for attempt in {1..60}; do
  if curl --fail --silent http://127.0.0.1:8000/health/ready >/dev/null; then
    break
  fi
  if [[ "$attempt" == 60 ]]; then
    echo 'Backend did not become ready' >&2
    exit 1
  fi
  sleep 2
done

curl --fail --silent http://127.0.0.1:8000/metrics >/dev/null
npm ci
npx playwright install --with-deps chromium
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1 npm run test:fullstack
python scripts/build-true-target-parity.py
