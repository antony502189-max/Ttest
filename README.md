# 112233.es

[Abrir 112233.es](https://112233.es/)

Marketplace full-stack de alquiler de habitaciones en Tenerife. El frontend conserva el diseño aprobado y consume una API FastAPI con PostgreSQL/PostGIS. Google Maps es el único proveedor cartográfico.

## Inicio local completo

Requisitos: Docker Compose, Python 3.12+, Node.js 22+ y npm.

```bash
git clone https://github.com/antony502189-max/Ttest.git
cd Ttest
cp .env.example .env.local
cp backend/.env.example backend/.env
docker compose up -d migrate backend mail-worker
npm ci
npm run dev
```

Servicios locales incluidos:

- PostgreSQL + PostGIS: `localhost:5432`;
- FastAPI/OpenAPI: `http://localhost:8000/api/docs`;
- Redis: `localhost:6379`;
- MinIO S3 API: `http://localhost:9000`;
- MinIO console: `http://localhost:9001`;
- Mailpit SMTP: `localhost:1025`;
- Mailpit UI: `http://localhost:8025`.

Para cargar datos de desarrollo:

```bash
docker compose --profile tools run --rm seed
```

Frontend `.env.local`:

```dotenv
VITE_GOOGLE_MAPS_API_KEY=
VITE_GOOGLE_MAPS_MAP_ID=
VITE_GOOGLE_CLIENT_ID=
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_ENABLE_MOCK_MODE=0
VITE_BASE_PATH=/Ttest/
```

Google Maps debe autorizar estos HTTP referrers:

```text
https://antony502189-max.github.io/Ttest/
https://antony502189-max.github.io/Ttest/*
```

## Backend без Docker

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e "backend[dev]"
cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

PostgreSQL с PostGIS всё равно должен быть доступен через `DATABASE_URL`. SQLite не является поддерживаемой production или integration-test базой.

## Почта

Письма создаются транзакционно в `mail_outbox`. Постоянный worker запускается сервисом `mail-worker`:

```bash
docker compose up -d mail-worker
```

В локальном Compose письма доставляются в Mailpit. В production обязательны реальные `SMTP_*` значения и постоянно работающий worker.

## Media

В обычном production-режиме используется S3-compatible storage. Локальный Compose уже подключает реальный MinIO и проверяет операции put/read/delete. Filesystem adapter остаётся для изолированной разработки и тестов.

## Полный локальный аудит

Полная проверка выполняется локально:

```bash
bash scripts/final-audit-local.sh
```

Скрипт:

1. поднимает PostGIS, Redis, MinIO и Mailpit;
2. создаёт отдельную `ttest_test`;
3. применяет Alembic с пустой базы;
4. запускает Ruff, Mypy и pytest;
5. проверяет PostgreSQL/PostGIS и MinIO integration tests;
6. запускает API, mail worker и seed;
7. выполняет frontend lint, typecheck и production build;
8. выполняет полный Playwright, a11y и visual suite;
9. выполняет отдельный real full-stack Playwright suite без mock backend.

Результаты Playwright сохраняются только в `output/` и исключены из Git.

CI берёт утверждённые snapshots из ветки `visual-baselines`, а actual/expected/diff и HTML-report публикует как GitHub Actions artifacts. Обычный CI никогда не обновляет baseline. Обновление разрешено только ручным запуском workflow **Update Approved Visual Baselines** после визуального ревью.

Отдельные команды:

```bash
npm run lint
npm run typecheck
npm run build
npm run test:e2e
npm run test:a11y
npm run test:visual
npm run test:fullstack

cd backend
ruff check app tests
mypy app
pytest -q
```

## Backup

Создать PostgreSQL backup:

```bash
docker compose --profile tools run --rm db-backup
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

- [Архитектура](docs/architecture.md)
- [API](docs/api.md)
- [База данных](docs/database.md)
- [Локальная разработка](docs/local-development.md)
- [Deployment](docs/deployment.md)
- [Design freeze](docs/frontend-freeze-report.md)
- [Тестирование](docs/test-report.md)
- [Финальный аудит](docs/final-audit.md)

## Stack

- React 19 + TypeScript + Vite 8
- FastAPI + SQLAlchemy async + Alembic
- PostgreSQL + PostGIS
- Redis
- MinIO/S3-compatible media storage
- Mail outbox + SMTP worker
- Prometheus metrics + structured JSON logs + optional Sentry
- Google Maps JavaScript API
- Playwright + axe-core
