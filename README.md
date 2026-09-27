# 112233.es

[![Full audit](https://github.com/antony502189-max/Ttest/actions/workflows/full-audit.yml/badge.svg?branch=main)](https://github.com/antony502189-max/Ttest/actions/workflows/full-audit.yml)
[![Production audit](https://github.com/antony502189-max/Ttest/actions/workflows/production-audit.yml/badge.svg?branch=main)](https://github.com/antony502189-max/Ttest/actions/workflows/production-audit.yml)
[![Mobile validation](https://github.com/antony502189-max/Ttest/actions/workflows/mobile-validation.yml/badge.svg?branch=main)](https://github.com/antony502189-max/Ttest/actions/workflows/mobile-validation.yml)

**112233.es** — full-stack marketplace аренды комнат и краткосрочного жилья на Канарских островах, в первую очередь на Tenerife. Проект включает пользовательский marketplace, публикацию и управление объявлениями, поиск по карте, импорт объявлений из внешних источников, админ-панель и модерацию, media pipeline для фото и видео, email/notification инфраструктуру и production deployment на VPS.

- Production frontend: [https://app.112233.es](https://app.112233.es)
- API prefix: <code>/api/v1</code>
- Backend: FastAPI
- Frontend: React + TypeScript + Vite
- Database: PostgreSQL + PostGIS
- Cache / distributed coordination: Redis
- Media storage: S3-compatible storage / MinIO
- Reverse proxy: Nginx внутри frontend-контейнера + внешний Traefik
- Current Alembic head in the repository: <code>0049_listing_video</code>

> README описывает текущую архитектуру ветки <code>main</code>. Production release является отдельным immutable release на VPS и определяется symlink <code>/srv/112233.es/current</code>, а не просто состоянием GitHub <code>main</code>.

---

## 1. Что сейчас реализовано

Проект уже не является статическим frontend-прототипом. Основной production path работает как полноценное клиент-серверное приложение.

### Marketplace

Пользователь может:

- искать объявления;
- переключаться между долгосрочной и краткосрочной арендой;
- фильтровать объявления по цене, датам, параметрам комнаты и требованиям;
- работать с картой Google Maps;
- использовать bounds/radius/polygon search через PostGIS;
- открывать карточку объявления;
- добавлять объявления в избранное;
- скрывать объявления из собственной выдачи;
- сохранять поиски;
- получать уведомления;
- просматривать public и owner-specific данные с разными уровнями приватности.

### Аккаунты

Поддерживаются:

- регистрация по email/password;
- обычный login;
- Google authentication;
- server-side refresh sessions;
- email verification;
- password reset;
- профиль пользователя;
- роли host / tenant;
- server-side administrator access;
- блокировки и moderation restrictions.

### Объявления пользователя

Host может:

- создать объявление;
- редактировать его;
- управлять статусом;
- закрыть или обновить объявление;
- удалить объявление;
- видеть его в <code>Mis anuncios / Tus anuncios</code>;
- различать долгосрочную и краткосрочную аренду в owner UI;
- загрузить фотографии;
- опционально добавить короткое видео.

Текущий media contract объявления:

| Ограничение | Значение |
|---|---:|
| Минимум фотографий | **5** |
| Максимум фотографий | **15** |
| Видео | **0 или 1** |
| Максимальная длительность видео | **30 секунд** |
| Input video | MP4 / MOV / M4V |
| Normalized video | MP4 H.264 + AAC |
| Max normalized video size | **24 MiB** |
| Max per-user media assets | **500** |
| Max per-user media storage | **2 GiB** |

Валидация выполняется не только во frontend, но и авторитетно на backend.

### External listings

Отдельный worker импортирует публичные объявления из настроенных внешних источников. В production Compose текущий default source set:

- Fotocasa;
- Milanuncios;
- PisoCompartido;
- Pisos;
- Alquiler Docente Canarias;
- Flatio.

Worker:

- выполняет discovery;
- загружает detail pages;
- нормализует данные;
- фильтрует нецелевые объявления;
- deduplicate-ит одинаковые объявления;
- объединяет разные источники в canonical listing;
- обновляет существующие записи идемпотентно;
- проверяет удалённые/недоступные объявления;
- закрывает canonical listing только когда исчез последний активный source;
- использует Redis distributed lock;
- поддерживает health/heartbeat state;
- не должен обходить CAPTCHA, authentication или access controls.

### Administration

Backend и frontend содержат production admin surface для:

- пользователей;
- объявлений;
- moderation restrictions;
- server-side administrator grants;
- audit history;
- external import state;
- operational diagnostics;
- promotions / homepage promotion state;
- moderation lifecycle.

Frontend role сам по себе не является security boundary: административный доступ проверяется backend.

---

## 2. Архитектура верхнего уровня

~~~mermaid
flowchart LR
    Browser["React SPA<br/>React 19 + TypeScript + Vite"]
    Nginx["Frontend Nginx<br/>static assets + /api proxy"]
    Traefik["Traefik<br/>TLS / public edge"]
    API["FastAPI modular monolith"]
    PG["PostgreSQL 16 + PostGIS"]
    Redis["Redis"]
    MinIO["MinIO / S3 storage"]
    Mail["SMTP provider"]
    MailWorker["Mail outbox worker"]
    ExternalWorker["External listings worker"]
    FFmpeg["ffmpeg / ffprobe"]

    Browser --> Traefik
    Traefik --> Nginx
    Nginx -->|"/api/v1"| API
    API --> PG
    API --> Redis
    API --> MinIO
    API --> FFmpeg
    MailWorker --> PG
    MailWorker --> Mail
    ExternalWorker --> PG
    ExternalWorker --> Redis
    ExternalWorker --> MinIO
~~~

Архитектурный стиль backend — **modular FastAPI monolith**. Бизнес-логика не распределена по микросервисам без необходимости. Фоновые задачи, которым нужен собственный lifecycle, запускаются отдельными процессами из того же backend package.

Основные runtime-процессы:

1. <code>frontend</code> — production Nginx + собранный React bundle;
2. <code>backend</code> — FastAPI;
3. <code>mail-worker</code> — доставка transactional mail outbox;
4. <code>external-listings-worker</code> — периодический импорт внешних объявлений;
5. <code>postgres</code> — PostgreSQL/PostGIS;
6. <code>redis</code> — rate limiting, locks и coordination;
7. <code>minio</code> — private S3-compatible media storage;
8. <code>migrate</code> — one-shot Alembic migration job.

---

## 3. Frontend

### Стек

- React 19;
- TypeScript;
- Vite 8;
- React Router;
- Radix UI primitives;
- Lucide icons;
- Tailwind utility infrastructure;
- custom CSS layers для точного mobile/desktop visual parity;
- Google Maps JavaScript API;
- Playwright для E2E, mobile, accessibility и visual tests.

### Routing

SPA использует <code>HashRouter</code>. Основные маршруты:

- <code>/</code> — главная;
- <code>/buscar</code> — поиск;
- <code>/habitacion/:id</code> — интерактивная карточка;
- <code>/acceso</code> — authentication;
- <code>/registro</code>;
- <code>/recuperar-contrasena</code>;
- <code>/restablecer-contrasena</code>;
- <code>/verificar-email</code>;
- <code>/favoritos</code>;
- <code>/notificaciones</code>;
- <code>/busquedas-guardadas</code>;
- <code>/perfil</code>;
- <code>/mis-anuncios</code>;
- <code>/publicar</code>;
- <code>/mis-anuncios/:id/editar</code>;
- <code>/admin</code>;
- legal/info routes.

Protected routes требуют восстановленной backend session. Admin route дополнительно выполняет server-side admin access check.

### Frontend transport boundary

Весь production HTTP transport сосредоточен в <code>src/api/</code>.

Ключевые модули:

- <code>auth.ts</code>;
- <code>client.ts</code>;
- <code>listings.ts</code>;
- <code>media.ts</code>;
- <code>admin.ts</code>;
- <code>moderation.ts</code>;
- <code>notifications.ts</code>;
- <code>reports.ts</code>;
- <code>search-history.ts</code>;
- <code>user-state.ts</code>;
- <code>users.ts</code>.

UI не должен напрямую собирать произвольные fetch-запросы к backend там, где уже существует API boundary.

### Application state

Основная production orchestration находится в <code>src/contexts/app-context.tsx</code>.

Context отвечает за:

- hydration session;
- public catalog;
- owner listings;
- create/edit/delete listing flows;
- media preparation;
- publication retry state;
- favorites;
- hidden listings;
- saved searches;
- profile;
- account deletion;
- moderation-aware behavior.

Для isolated browser tests существует mock provider. Production работает с <code>VITE_ENABLE_MOCK_MODE=0</code>.

### Responsive UI

Проект содержит отдельные mobile parity passes и screenshot-driven regression tests. Mobile layout не является просто уменьшенной desktop-версией: отдельные surfaces имеют собственную компоновку.

Особенно тестируются:

- search;
- listing detail;
- publish/edit;
- owner listings;
- auth;
- admin;
- navigation;
- media actions.

---

## 4. Backend

Backend находится в <code>backend/</code> и требует Python 3.12+.

Основные технологии:

- FastAPI;
- SQLAlchemy async;
- asyncpg;
- Alembic;
- Pydantic Settings;
- PostgreSQL/PostGIS;
- Redis;
- boto3;
- Pillow;
- ffmpeg/ffprobe;
- PyJWT;
- argon2;
- Google auth validation;
- Prometheus client;
- Sentry integration.

### Backend layers

~~~text
backend/app/
├── api/
│   ├── public_pages.py
│   └── v1/
│       ├── admin.py
│       ├── auth.py
│       ├── favorites.py
│       ├── listings.py
│       ├── notifications.py
│       ├── reports.py
│       ├── saved_searches.py
│       ├── search_history.py
│       ├── uploads.py
│       └── users.py
├── core/              # config, rate limits, observability, media limits, security helpers
├── db/                # engine/session
├── schemas/           # Pydantic request/response contracts
├── services/          # business logic
├── commands/          # operational/background commands
├── workers/           # persistent workers
├── external_sources.py
├── storage.py
├── models.py / models/
└── main.py
~~~

### FastAPI application

<code>backend/app/main.py</code> отвечает за:

- startup/runtime validation;
- routers;
- CORS;
- request IDs;
- security headers;
- rate limiting;
- Prometheus metrics;
- structured request logging;
- Sentry;
- readiness/health;
- listing expiry lifecycle loop;
- production OpenAPI policy.

В production interactive OpenAPI отключён. В development/test доступен:

- <code>/api/docs</code>;
- <code>/api/openapi.json</code>.

---

## 5. API

Base prefix:

~~~text
/api/v1
~~~

Крупные API domains:

| Domain | Назначение |
|---|---|
| <code>/auth</code> | login, register, Google auth, refresh, logout, email verification, password reset |
| <code>/listings</code> | search, public details, owner CRUD, lifecycle |
| <code>/uploads</code> | image upload |
| <code>/uploads/video</code> | video upload + normalization |
| <code>/media/:id</code> | authenticated/public media delivery |
| <code>/favorites</code> | favorites |
| <code>/discarded-listings</code> | user-hidden listings |
| <code>/saved-searches</code> | saved search state |
| <code>/search-history</code> | recent search state |
| <code>/notifications</code> | user notifications |
| <code>/reports</code> | listing reports |
| <code>/users</code> | profile/account |
| <code>/admin</code> | moderation/admin/operational endpoints |

Errors имеют machine-readable форму с error code и, где применимо, field errors.

---

## 6. Authentication и sessions

### Access token

Access token хранится frontend-ом в runtime memory и передаётся:

~~~http
Authorization: Bearer <access-token>
~~~

### Refresh token

Refresh token:

- server-generated;
- хранится в HttpOnly cookie;
- имеет path <code>/api/v1/auth</code>;
- Secure в production;
- session хранится и может быть отозвана на backend.

Это позволяет не хранить refresh token в LocalStorage.

### Login methods

Поддерживаются:

- email/password;
- Google identity;
- password reset;
- email verification.

### Email verification

Verification state участвует в publication flow. Verification и reset records не хранят raw token в базе.

### Security controls

В проекте есть:

- Argon2 password hashing;
- JWT secret validation;
- отдельный HMAC secret для email verification;
- explicit CORS allowlist;
- secure refresh cookies;
- request origin checks для cookie-mutating auth endpoints;
- per-IP rate limits;
- Redis-backed production limiting;
- X-Request-ID;
- security headers;
- restricted production runtime validation;
- dependency/security CI checks.

---

## 7. Database и migrations

Production database — PostgreSQL 16 + PostGIS.

Alembic chain начинается с <code>0001_core.py</code> и на текущем <code>main</code> заканчивается:

~~~text
0049_listing_video.py
~~~

Исторические migrations в production считаются immutable. Production audit проверяет migration history и не допускает тихого переписывания уже deployed revisions.

### Основные группы данных

Схема содержит сущности для:

- users;
- auth sessions;
- password reset;
- email verification;
- admin access;
- user/listing restrictions;
- listings;
- listing images;
- listing video;
- media assets;
- external sources;
- canonical external listing lifecycle;
- favorites;
- discarded listings;
- saved searches;
- search history;
- notifications;
- reports;
- listing views;
- listing status history;
- promotions;
- mail outbox;
- audit logs;
- storage deletion retry state;
- external import run/worker state.

### Геоданные

PostGIS используется для:

- public listing location;
- geographic filtering;
- bounds search;
- radius search;
- polygon search;
- spatial indexes.

Public API не должен раскрывать private owner location автоматически. Owner/admin endpoints имеют отдельный privacy contract.

---

## 8. Lifecycle объявления

У объявления есть server-authoritative lifecycle.

Основные состояния включают:

- draft;
- pending;
- published;
- hidden;
- rejected;
- closed.

Frontend отображает локализованные пользовательские статусы, но authoritative state хранится на backend.

Backend также:

- обрабатывает expiry;
- скрывает expired listing из public visibility;
- учитывает user/listing moderation restrictions;
- сохраняет owner management access там, где это допустимо;
- не даёт public media URL обходить visibility policy.

---

## 9. Media pipeline

Media — одна из самых важных частей текущей архитектуры.

### 9.1 Фото

Accepted input:

- JPEG;
- PNG;
- WebP.

Backend не доверяет расширению файла. Pillow реально декодирует изображение и валидирует:

- format;
- dimensions;
- pixel count;
- corrupted image data;
- decompression-bomb conditions.

После загрузки изображение:

1. проходит EXIF orientation normalization;
2. приводится к browser-oriented image;
3. уменьшается до configured max dimension;
4. кодируется в WebP;
5. получает perceptual hash;
6. получает responsive variants.

Текущие variants:

- <code>full</code>;
- <code>card</code>;
- <code>thumb</code>.

Это позволяет карточкам не скачивать исходное полноразмерное изображение.

### 9.2 Фото объявления

Publication contract:

~~~text
5 <= listing photos <= 15
~~~

Проверка есть на frontend и backend.

### 9.3 Видео

На объявление разрешено максимум одно optional video.

Input:

- MP4;
- MOV;
- M4V-compatible container.

Backend выполняет:

1. content-type/container validation;
2. <code>ffprobe</code>;
3. проверку duration/dimensions;
4. <code>ffmpeg</code> normalization;
5. scale до configured maximum;
6. H.264 encoding;
7. AAC audio;
8. YUV420p;
9. <code>+faststart</code>;
10. повторный <code>ffprobe</code>;
11. output-size validation.

Current encoding policy включает:

- maximum 30 seconds;
- maximum dimension 1920;
- H.264 <code>libx264</code>;
- <code>veryfast</code>;
- CRF 26;
- max video rate 4 Mbit/s;
- AAC 128 kbit/s;
- normalized output <= 24 MiB.

### 9.4 Video delivery

Видео не должно полностью загружаться из S3/MinIO в RAM ради небольшого browser seek.

Media endpoint поддерживает HTTP byte ranges, а storage abstraction предоставляет <code>get_range()</code>.

Текущий server-side chunk budget — до 1 MiB на отдельный returned range chunk.

### 9.5 Storage

Production:

~~~text
FastAPI -> S3 adapter -> private MinIO bucket
~~~

Объекты не являются публичным bucket content. Доступ идёт через backend media endpoint, потому что backend обязан проверить:

- asset existence;
- owner;
- listing status;
- moderation restrictions;
- expiry;
- public visibility.

### 9.6 Cleanup

Media lifecycle учитывает:

- failed publication;
- retry;
- edit replacement;
- listing deletion;
- account deletion;
- orphaned uploads;
- storage delete failures.

Для failed physical deletes существует durable retry path.

---

## 10. Publication flow

Упрощённый create flow:

~~~mermaid
sequenceDiagram
    participant U as User
    participant F as React
    participant M as Media API
    participant L as Listings API
    participant S as S3/MinIO
    participant D as PostgreSQL

    U->>F: fills listing form
    F->>F: validates required fields and 5-15 photos
    F->>M: uploads/prepares photos and optional video
    M->>S: stores normalized objects
    M->>D: creates media asset rows
    M-->>F: asset IDs
    F->>L: create listing with asset IDs
    L->>D: validates ownership + listing contract
    L->>D: commits listing + media relationships
    L-->>F: canonical listing
~~~

Frontend хранит prepared-media retry state для того, чтобы повторный publication attempt не создавал бессмысленные duplicate uploads после сетевой ошибки.

Backend остаётся authoritative: прямой API request не должен обходить photo/video limits или ownership checks.

---

## 11. Search и privacy

Search API поддерживает domain filtering и geographic filtering.

### Geographic search

PostGIS используется для:

- viewport bounds;
- radius;
- polygon;
- public map points.

### Private address

Для owner-created listings backend разделяет public location representation и private owner data.

Public consumer не должен получать:

- точный street;
- private postcode;
- exact owner coordinates,

если endpoint contract этого не разрешает.

### Maps

Frontend использует Google Maps. Map key должен быть ограничен production HTTP referrers и только необходимыми API.

---

## 12. External import architecture

<code>external-listings-worker</code> — отдельный long-running process.

### Full import cycle

~~~mermaid
flowchart TD
    Start["worker cycle"]
    Lock["Redis distributed lock"]
    Sources["configured source adapters"]
    Discover["discover URLs"]
    Fetch["fetch detail"]
    Normalize["normalize + validate room offer"]
    Canonical["canonical deduplication"]
    Upsert["PostgreSQL upsert"]
    Media["optional image import to MinIO"]
    Health["worker heartbeat / run state"]

    Start --> Lock
    Lock --> Sources
    Sources --> Discover
    Discover --> Fetch
    Fetch --> Normalize
    Normalize --> Canonical
    Canonical --> Upsert
    Upsert --> Media
    Media --> Health
~~~

### Safety rules

Importer не должен:

- обходить authentication;
- решать CAPTCHA;
- обходить robots/access controls;
- считать blocked source пустым source;
- массово закрывать объявления из-за временной ошибки источника.

Если один source временно не работает, это не должно автоматически уничтожать canonical catalog.

### Deduplication

Проект поддерживает canonical merging. Одно и то же физическое предложение, найденное в нескольких sources, не должно становиться несколькими одинаковыми карточками.

Perceptual photo hash также используется как один из сигналов для conservative duplicate checks.

---

## 13. Mail и notifications

Transactional email не отправляется непосредственно внутри HTTP request.

Используется схема:

~~~text
HTTP transaction
    -> mail_outbox row
        -> mail-worker
            -> SMTP
~~~

Преимущества:

- HTTP request не блокируется на SMTP;
- запись письма коммитится вместе с business transaction;
- delivery имеет retry policy;
- production worker имеет healthcheck.

В local Compose SMTP направлен в Mailpit.

---

## 14. Moderation

Moderation реализована server-side.

Есть restriction model для:

- user;
- listing.

Примеры user restrictions:

- full account restriction;
- publish restriction;
- listing-view restriction.

Restrictions могут быть:

- временными;
- бессрочными;
- досрочно revoked.

Public visibility listings и media учитывает активные restrictions.

Администраторский frontend не является источником истины: backend отдельно авторизует каждую admin operation.

Подробно: [docs/admin-moderation.md](docs/admin-moderation.md).

---

## 15. SEO и public documents

Интерактивное приложение использует HashRouter, но production не полагается только на client-side SPA для всех crawler-facing ресурсов.

Nginx проксирует в FastAPI:

- canonical public listing documents;
- <code>/sitemap.xml</code>;
- <code>/robots.txt</code>.

Legal pages доступны прямыми путями.

Private/account application paths получают anti-indexing headers.

---

## 16. Production topology

Production работает на VPS через Docker Compose.

~~~mermaid
flowchart LR
    Internet --> Traefik
    Traefik --> Frontend["frontend / nginx"]
    Frontend --> Backend["backend / FastAPI"]
    Backend --> PG["PostgreSQL/PostGIS"]
    Backend --> Redis
    Backend --> MinIO
    Backend --> SMTP
    MailWorker --> PG
    MailWorker --> SMTP
    ImportWorker["external-listings-worker"] --> PG
    ImportWorker --> Redis
    ImportWorker --> MinIO
~~~

PostgreSQL, Redis, MinIO и FastAPI не публикуют свои ports в Internet.

Внешний public edge — Traefik.

### Production networks

Compose разделяет:

- internal data network;
- internal application network;
- egress network;
- external Traefik network.

### Container hardening

Production Compose использует, где применимо:

- read-only filesystem;
- tmpfs;
- dropped Linux capabilities;
- <code>no-new-privileges</code>;
- PID limits;
- healthchecks;
- pinned stateful image digests.

---

## 17. Immutable deployment model

Production release не запускается прямо из mutable checkout.

Server layout:

~~~text
/srv/112233.es/
├── repo/                    # fetch/cache checkout
├── releases/
│   └── <40-char-git-sha>/   # immutable git worktree
├── current -> releases/...  # active release symlink
├── shared/
│   ├── production.env
│   └── release.lock
└── backups/
~~~

### Deploy

Штатный deploy:

~~~bash
/srv/112233.es/releases/<sha>/deploy/deploy-release.sh <40-character-main-sha>
~~~

Script принимает только точный current <code>origin/main</code> SHA.

Для существующей installation deploy выполняет примерно такой sequence:

1. проверяет immutable release worktree;
2. валидирует production env/Compose;
3. проверяет compatibility stateful service images;
4. останавливает application writers;
5. создаёт production backups;
6. запускает dependencies нового release;
7. запускает Alembic migration;
8. выполняет maintenance cleanup;
9. build/start backend/workers/frontend;
10. ждёт backend readiness;
11. переключает <code>current</code>;
12. запускает external production smoke test;
13. помечает release successful.

При ошибке работает bounded rollback path.

### Deploy locking

Deploy, rollback, backup и restore verification используют один <code>flock</code>. Параллельная release operation завершается до изменения production state.

### Rollback

Rollback выбирает предыдущий recorded release и не должен:

- удалять volumes;
- запускать destructive reverse migrations;
- менять stateful image family без отдельного migration plan.

Полная документация: [docs/production-operations.md](docs/production-operations.md).

---

## 18. Local development

### Requirements

Рекомендуется:

- Docker + Docker Compose;
- Node.js 22+;
- npm;
- Python 3.12+ для backend tooling вне Docker.

### Полный локальный запуск

~~~bash
git clone https://github.com/antony502189-max/Ttest.git
cd Ttest

cp .env.example .env.local

docker compose up -d migrate backend mail-worker external-listings-worker

npm ci
npm run dev
~~~

Frontend:

~~~text
http://localhost:5173
~~~

Backend:

~~~text
http://localhost:8000
~~~

Development OpenAPI:

~~~text
http://localhost:8000/api/docs
~~~

### Local services

| Service | Address |
|---|---|
| PostgreSQL/PostGIS | <code>localhost:5432</code> |
| Redis | <code>localhost:6379</code> |
| MinIO S3 API | <code>localhost:9000</code> |
| MinIO Console | <code>localhost:9001</code> |
| Mailpit SMTP | <code>localhost:1025</code> |
| Mailpit UI | <code>localhost:8025</code> |
| FastAPI | <code>localhost:8000</code> |
| Vite | <code>localhost:5173</code> |

### Demo/seed data

~~~bash
docker compose --profile tools run --rm seed
~~~

Seed command запрещён production runtime configuration.

---

## 19. Frontend environment

Минимальный local <code>.env.local</code>:

~~~dotenv
VITE_GOOGLE_MAPS_API_KEY=
VITE_GOOGLE_MAPS_MAP_ID=
VITE_GOOGLE_CLIENT_ID=
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_ENABLE_MOCK_MODE=0
BACKEND_PORT=8000
~~~

Не коммить реальные production credentials.

---

## 20. Backend без Docker

~~~bash
python -m venv .venv
source .venv/bin/activate

# Windows:
# .venv\Scripts\activate

python -m pip install -e "backend[dev]"

cd backend
alembic upgrade head
uvicorn app.main:app --reload
~~~

Для backend нужен настоящий PostgreSQL/PostGIS через <code>DATABASE_URL</code>. SQLite не является production/integration-test database для этого проекта.

---

## 21. Основные production environment groups

Полный template: [deploy/production.env.example](deploy/production.env.example).

### Database

- <code>DATABASE_URL</code>
- pool/overflow limits;
- statement timeout;
- lock timeout;
- idle transaction timeout.

### Authentication

- <code>JWT_SECRET</code>
- <code>EMAIL_VERIFICATION_HMAC_SECRET</code>
- <code>GOOGLE_CLIENT_ID</code>
- active-session limits.

### Redis

- <code>REDIS_URL</code>

### Storage

- <code>S3_BUCKET</code>
- <code>S3_ENDPOINT_URL</code>
- <code>S3_ACCESS_KEY</code>
- <code>S3_SECRET_KEY</code>
- connection/read timeout settings.

### Media

- image upload limit;
- image dimensions/pixels;
- image processing concurrency;
- video upload/output limit;
- video duration;
- video max dimension;
- video processing concurrency;
- per-user asset/byte quotas.

### Email

- SMTP host/port;
- user/password;
- from address;
- TLS policy;
- worker retry/lease configuration.

### External import

- enable switch;
- run interval;
- enabled sources;
- minimum healthy sources;
- request timeout;
- per-source concurrency;
- image download behavior;
- removal check;
- worker stale timeout.

---

## 22. Testing

### Frontend

~~~bash
npm ci
npm run lint
npm run typecheck
npm run build

npm run test:e2e
npm run test:a11y
npm run test:visual
npm run test:fullstack
npm run test:security
npm run test:bundle-security
~~~

### Backend

~~~bash
cd backend

ruff check app tests
mypy app
pytest -q
~~~

Integration tests требуют PostgreSQL/PostGIS. S3 tests требуют S3-compatible endpoint.

### Complete audit

~~~bash
bash scripts/final-audit-local.sh
~~~

Audit включает:

- infrastructure startup;
- empty-database migrations;
- backend lint/typecheck/tests;
- PostgreSQL/PostGIS integration;
- MinIO integration;
- frontend lint/typecheck/build;
- Playwright suites;
- accessibility checks;
- visual parity;
- real frontend/backend full-stack tests.

---

## 23. CI

Основные GitHub Actions workflows:

### Full audit

<code>.github/workflows/full-audit.yml</code>

Проверяет complete application path. Для PR запускает real full-stack audit, для <code>main</code> — полный local-style audit.

### Production audit

<code>.github/workflows/production-audit.yml</code>

Проверяет:

- supply-chain pins;
- production Compose;
- nginx;
- migration chain;
- backend Ruff/Mypy;
- backend unit/integration/S3 tests;
- frontend lint/typecheck/build;
- dependency security;
- production bundle security;
- static file permissions.

### Mobile validation

Проверяет mobile E2E, owner flows, publication/auth и visual/mobile regressions.

### Capacity smoke safeguards

Проверяет capacity assumptions и защитные лимиты.

### Audit Source Snapshot

Контролирует состояние audit/source snapshot contract.

### External source contract

Проверяет importer contract и lifecycle внешних объявлений.

### Visual baselines

Approved visual snapshots живут отдельно от обычного PR flow. CI не должен самовольно обновлять expected baselines.

---

## 24. Repository structure

~~~text
Ttest/
├── .github/
│   └── workflows/                 # CI / audits
├── backend/
│   ├── alembic/
│   │   └── versions/              # database migrations 0001..0049
│   ├── app/
│   │   ├── api/                   # FastAPI routers
│   │   ├── commands/              # operational commands
│   │   ├── core/                  # config/security/observability/limits
│   │   ├── db/                    # SQLAlchemy session/engine
│   │   ├── schemas/               # Pydantic contracts
│   │   ├── services/              # business logic
│   │   ├── workers/               # persistent workers
│   │   ├── external_sources.py    # source adapters
│   │   ├── main.py                # FastAPI application
│   │   └── storage.py             # local/S3 abstraction
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
├── deploy/
│   ├── deploy-release.sh
│   ├── rollback-release.sh
│   ├── backup-*.sh
│   ├── restore-*.sh
│   ├── smoke-production.sh
│   ├── nginx.conf
│   └── production.env.example
├── docs/                           # deeper technical/operational docs
├── public/                         # static public assets/legal docs
├── scripts/                        # audits, validation, utilities
├── src/
│   ├── api/                        # frontend API boundary
│   ├── components/
│   ├── contexts/
│   ├── data/
│   ├── hooks/
│   ├── lib/
│   ├── pages/
│   ├── App.tsx
│   └── index.css
├── tests/                          # Playwright / frontend contract tests
├── docker-compose.yml              # local stack
├── docker-compose.production.yml   # VPS production stack
├── Dockerfile                      # frontend build/runtime
├── package.json
└── README.md
~~~

---

## 25. Observability

Backend поддерживает:

- structured logs;
- request IDs;
- Prometheus metrics;
- request latency/count metrics;
- worker health state;
- readiness healthchecks;
- optional Sentry.

Production release injects Git SHA как release identifier.

---

## 26. Backup и recovery

Local PostgreSQL backup:

~~~bash
docker compose --profile tools run --rm db-backup
~~~

Production имеет отдельные scripts для:

- PostgreSQL backup;
- MinIO backup;
- restore verification;
- rollback.

Production backup/restore procedures нельзя заменять ручным удалением volumes или <code>docker compose down -v</code>.

См. [docs/production-operations.md](docs/production-operations.md).

---

## 27. Ключевые инварианты проекта

При изменениях особенно важно сохранять следующие правила.

### Security

- frontend не является security boundary;
- admin authorization проверяется backend;
- media visibility проверяется backend;
- private address не должен утекать в public API;
- production не должен запускаться с development secrets/config.

### Listings

- backend authoritative;
- create/edit должны иметь одинаковые validation rules;
- минимум 5 и максимум 15 фото;
- максимум одно видео;
- video <= 30 seconds;
- media asset должен принадлежать текущему пользователю;
- один video asset не должен случайно использоваться несколькими listings.

### Media

- bucket private;
- thumbnails/cards используют appropriate variants;
- video seek использует Range;
- orphan cleanup обязателен;
- storage failure не должен превращаться в silent data leak.

### External import

- import идемпотентный;
- temporary source failure не равен removal;
- duplicate sources должны объединяться;
- последний исчезнувший source закрывает canonical listing.

### Deployment

- deploy только merged <code>main</code> SHA;
- backup до migrations;
- immutable release directories;
- smoke check до final success;
- rollback path всегда сохраняется.

---

## 28. Что активно развивается в текущем коде

По текущей структуре и последним migrations/flows основные зоны активной разработки:

1. **Listing media**
   - 5–15 photos;
   - video;
   - responsive image variants;
   - storage quotas;
   - media lifecycle;
   - Range delivery.

2. **Owner listing UX**
   - mobile <code>Tus anuncios</code>;
   - owner-only actions;
   - edit/delete;
   - rental-mode presentation;
   - create/edit parity.

3. **External catalog**
   - source quality;
   - deduplication;
   - source lifecycle;
   - removal verification;
   - worker health.

4. **Admin/moderation**
   - restrictions;
   - admin access;
   - auditability;
   - operational state.

5. **Production hardening**
   - immutable deployments;
   - backup/restore;
   - capacity safeguards;
   - supply-chain pinning;
   - security checks.

6. **Mobile/visual parity**
   - screenshot-driven UI fixes;
   - responsive owner/publish/search/detail flows;
   - visual regression protection.

---

## 29. Где искать подробности

- [Architecture](docs/architecture.md)
- [API](docs/api.md)
- [Database](docs/database.md)
- [Local development](docs/local-development.md)
- [Production operations](docs/production-operations.md)
- [Production monitoring](docs/production-monitoring.md)
- [Admin & moderation](docs/admin-moderation.md)
- [External import catalog contract](docs/external-import-catalog-contract.md)
- [Capacity smoke](docs/capacity-smoke.md)
- [Final audit](docs/final-audit.md)
- [Test report](docs/test-report.md)

---

## 30. Коротко: как думать о проекте

Если нужно быстро понять систему, модель такая:

~~~text
React SPA
  -> src/api
    -> Nginx /api proxy
      -> FastAPI
        -> PostgreSQL/PostGIS        # source of truth
        -> Redis                     # rate limits + distributed locks
        -> MinIO                     # private media objects
        -> mail_outbox               # transactional email queue

mail-worker
  -> mail_outbox -> SMTP

external-listings-worker
  -> public source adapters
  -> normalize/deduplicate
  -> PostgreSQL + MinIO

deploy-release.sh
  -> backup
  -> migrate
  -> start release
  -> readiness
  -> smoke
  -> immutable current release
~~~

**Source of truth — backend + PostgreSQL. Frontend отвечает за UX, но не за security или authoritative business validation.**
