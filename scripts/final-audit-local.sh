#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

AUDIT_VENV="${AUDIT_VENV:-$ROOT/.audit-venv}"
TEST_DATABASE_URL="${TEST_DATABASE_URL:-postgresql+asyncpg://ttest:ttest@127.0.0.1:5432/ttest_test}"

cleanup() {
  docker compose logs --no-color backend mail-worker > output/backend-audit.log 2>&1 || true
}
trap cleanup EXIT

mkdir -p output backups

echo '[1/9] Starting local infrastructure'
docker compose up -d postgres redis minio minio-init mailpit

until docker compose exec -T postgres pg_isready -U ttest -d postgres >/dev/null 2>&1; do sleep 2; done

echo '[2/9] Creating isolated PostgreSQL/PostGIS test database'
if ! docker compose exec -T postgres psql -U ttest -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='ttest_test'" | grep -q 1; then
  docker compose exec -T postgres createdb -U ttest ttest_test
fi

echo '[3/9] Installing local backend audit environment'
python3 -m venv "$AUDIT_VENV"
"$AUDIT_VENV/bin/python" -m pip install --upgrade pip
"$AUDIT_VENV/bin/python" -m pip install -e "$ROOT/backend[dev]"

export APP_ENV=test
export DATABASE_URL="$TEST_DATABASE_URL"
export TEST_DATABASE_URL
export JWT_SECRET='local-audit-secret-at-least-32-characters'
export AUTO_PUBLISH_LISTINGS=true
export FRONTEND_ORIGINS='http://testserver,http://127.0.0.1:4174'
export MEDIA_ROOT="$ROOT/backend/var/test-media"
export STORAGE_BACKEND=local
export REDIS_URL='redis://127.0.0.1:6379/15'

pushd backend >/dev/null

echo '[4/9] Backend lint, typecheck and migrations'
"$AUDIT_VENV/bin/ruff" check app tests
"$AUDIT_VENV/bin/ruff" format --check app tests
"$AUDIT_VENV/bin/mypy" app
"$AUDIT_VENV/bin/alembic" upgrade head

echo '[5/9] Backend unit and PostgreSQL/PostGIS integration tests'
"$AUDIT_VENV/bin/pytest" -q -m 'not integration'
"$AUDIT_VENV/bin/pytest" -q -m 'integration and not s3'

export S3_ENDPOINT_URL='http://127.0.0.1:9000'
export S3_BUCKET='ttest-media'
export S3_REGION='us-east-1'
export S3_ACCESS_KEY='ttest-minio'
export S3_SECRET_KEY='ttest-minio-secret'
"$AUDIT_VENV/bin/pytest" -q -m 's3'
popd >/dev/null

echo '[6/9] Starting migrated development backend and mail worker'
docker compose up -d migrate backend mail-worker
docker compose --profile tools run --rm seed
until curl --fail --silent http://127.0.0.1:8000/health/ready >/dev/null; do sleep 2; done
curl --fail --silent http://127.0.0.1:8000/metrics >/dev/null

echo '[7/9] Frontend static checks and production build'
npm ci
npm run lint
npm run typecheck
VITE_BASE_PATH=/Ttest/ VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1 npm run build

# Playwright installation is idempotent and does not use GitHub Actions.
npx playwright install chromium

echo '[8/9] Complete mock-mode regression, accessibility and visual suites'
VITE_ENABLE_MOCK_MODE=1 VITE_E2E_BYPASS_ONBOARDING=1 npm run test:e2e
VITE_ENABLE_MOCK_MODE=1 VITE_E2E_BYPASS_ONBOARDING=1 npm run test:a11y
VITE_ENABLE_MOCK_MODE=1 VITE_E2E_BYPASS_ONBOARDING=1 npm run test:visual

echo '[9/9] Real frontend + FastAPI + PostgreSQL full-stack suite'
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1 npm run test:fullstack

echo 'LOCAL FINAL AUDIT PASSED'
