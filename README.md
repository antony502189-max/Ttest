# 112233.es — marketplace de alquiler

Full-stack marketplace with a React/Vite frontend and a FastAPI/PostgreSQL backend.

## Start the complete local stack

```bash
docker compose up -d --build
```

Services:

- frontend: `http://localhost:4174`
- API: `http://localhost:8000/api/v1`
- OpenAPI: `http://localhost:8000/docs`
- PostgreSQL/PostGIS: `localhost:5432`
- Redis: `localhost:6379`
- MinIO API: `http://localhost:9000`
- MinIO console: `http://localhost:9001`
- Mailpit SMTP: `localhost:1025`
- Mailpit UI: `http://localhost:8025`

Run migrations and seed the development dataset:

```bash
docker compose up -d postgres redis minio minio-init mailpit
docker compose run --rm migrate
docker compose --profile tools run --rm seed
docker compose up -d backend mail-worker frontend
```

The seed command is idempotent and refuses to run when `APP_ENV=production`.

## Frontend

```bash
npm ci
npm run dev
```

Important variables are listed in `.env.example`. The browser uses the real backend by default. Local-only mock mode is explicit:

```bash
VITE_ENABLE_MOCK_MODE=1 npm run dev
```

## Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
uvicorn app.main:app --reload
```

Copy `backend/.env.example` to `backend/.env` and set local credentials as needed.

## Database

PostgreSQL with PostGIS is mandatory. Apply all migrations from an empty database:

```bash
cd backend
alembic upgrade head
alembic current
```

PostgreSQL с PostGIS всё равно должен быть доступен через `DATABASE_URL`. SQLite не является поддерживаемой production или integration-test базой.

## Mail

The application writes verification and password-reset messages into `mail_outbox`. Start the persistent worker:

```bash
cd backend
python -m app.commands.outbox_worker
```

В локальном Compose письма доставляются в Mailpit. В production обязательны реальные `SMTP_*` значения и постоянно работающий worker.

## Media storage

В обычном production-режиме используется S3-compatible storage. Локальный Compose уже подключает реальный MinIO и проверяет операции put/read/delete. Filesystem adapter остаётся для изолированной разработки и тестов.

## Quality gates

Backend:

```bash
cd backend
ruff check app tests
mypy app
pytest -q
```

Frontend:

```bash
npm run lint
npm run typecheck
npm run build
npm run test:bundle-security
npm run test:e2e
npm run test:a11y
npm run test:visual
npm run test:fullstack
```

Complete local audit:

```bash
bash scripts/final-audit-local.sh
```

The script:

1. starts PostGIS, Redis, MinIO and Mailpit;
2. creates an isolated test database;
3. installs a clean constrained backend environment;
4. applies the complete Alembic chain;
5. runs Ruff, Mypy, unit, PostgreSQL/PostGIS and MinIO tests;
6. starts the migrated backend and mail worker;
7. performs frontend lint, typecheck and production build;
8. runs complete Playwright mock-mode regression, a11y and visual suites;
9. runs the real frontend + FastAPI + PostgreSQL full-stack suite.

## Backups

Local helpers:

```bash
docker compose --profile tools run --rm db-backup
docker compose --profile tools run --rm db-restore -- --file /backups/ttest-YYYYMMDDTHHMMSSZ.dump
docker compose --profile tools run --rm minio-backup
docker compose --profile tools run --rm minio-restore -- --file /backups/minio-YYYYMMDDTHHMMSSZ.tar.gz
```

Файлы появляются в локальном каталоге `backups/`, который исключён из Git. Production использует self-hosted PostGIS volume и проверяемую backup/restore-процедуру на VPS; см. [Production operations](docs/production-operations.md).

## Production checklist

Перед production deployment обязательны:

- DNS `app.112233.es`, направленный на VPS, и HTTPS через существующий Traefik;
- точные HTTPS origins в `FRONTEND_ORIGINS`;
- сильный `JWT_SECRET` и отдельный независимый `EMAIL_VERIFICATION_HMAC_SECRET`;
- self-hosted PostgreSQL/PostGIS, Redis и MinIO с persistent volumes;
- SMTP и outbox worker;
- Google OAuth client для production origins;
- Google Maps HTTP-referrer/API restrictions;
- `SENTRY_DSN` или другой error-tracking provider;
- reverse proxy с TLS и ограничениями размера request body.

GitHub Pages не является production-поверхностью этого проекта. Production frontend и API работают на VPS за `https://app.112233.es`, используют `/api/v1` и `VITE_ENABLE_MOCK_MODE=0`. Команды deploy, backup, restore и rollback описаны в [Production operations](docs/production-operations.md).

Backend специально отказывается запускаться в `APP_ENV=production`, если критическая конфигурация небезопасна или отсутствует.

## Документация

- [Architecture](docs/architecture.md)
- [API surface](docs/api.md)
- [Database and migrations](docs/database.md)
- [Test report](docs/test-report.md)
- [Final audit](docs/final-audit.md)
- [Production operations](docs/production-operations.md)
