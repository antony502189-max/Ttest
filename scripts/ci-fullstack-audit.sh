#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Backend lint, migrations, unit, PostgreSQL, and MinIO tests run in the
# independent Production audit job. This job exercises the real HTTP stack.
bash scripts/start-fullstack-audit.sh

npm ci
npx playwright install --with-deps chromium
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1 npm run test:fullstack
python scripts/build-true-target-parity.py
