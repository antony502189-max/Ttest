# Final implementation audit

Audit baseline: Codex result ending at `e46b45a596566b1470328d6a3b8d7755cdbd50d6`.

> Historical audit record. This document describes the implementation state at the baseline above. The current release gate also runs GitHub Actions (`Audit Source Snapshot`, `Production audit`, `Mobile validation` and `Full audit`), while `scripts/final-audit-local.sh` remains the reproducible local equivalent. The current migration head is documented in `docs/database.md`.

## Codex report findings reviewed

The following reported gaps were confirmed and addressed in code:

- route-level business logic;
- missing PostgreSQL/PostGIS integration coverage;
- incomplete browser/a11y/full-stack audit path;
- S3 adapter not tested against a real compatible service;
- mail outbox without a persistent worker;
- messages/reports still persisted locally;
- single-process rate limiting;
- missing metrics, structured logs, error tracking and backup tooling;
- incomplete production configuration validation.

## Additional defects found during audit

- mobile room filters `1–10` and `10+` were not sent to the backend;
- holiday listing price sort/filter could use the wrong price column;
- public avatars could return `404` in normal `<img>` requests;
- cross-origin media headers were incompatible with the GitHub Pages frontend;
- message thread listing performed an N+1 query for previews;
- guest-state import could fail completely because of one legacy slug id;
- partial image-upload failures could leave orphan assets;
- full-stack Playwright API URLs incorrectly dropped `/api/v1`;
- full-stack room-filter test depended on execution order;
- database integrity depended too heavily on Pydantic instead of PostgreSQL constraints.

## Implemented

### Architecture

FastAPI routes for auth, listings, users, messages, reports, admin, favorites, saved searches and search history now delegate to service/repository layers. HTTP adapters retain only request dependencies, status codes, cookie handling and response mapping.

### PostgreSQL/PostGIS

At this audit baseline, the migration head was `0015_integrity_constraints`. It normalized legacy data and added database-level checks for listing prices, deposit, room size, bedroom count, residents, capacity, minimum stay, dates and rental-mode primary price. It added partial/composite indexes for public search, owner listings, room counts and pending outbox delivery. Later migrations are tracked in `docs/database.md`; deployments must always run `alembic upgrade head` rather than target this historical revision explicitly.

Server search supports:

- query/city/area;
- rental mode and correct primary price;
- room type(s);
- room count `1–10` and `10+`;
- all existing property and tenant filters;
- bounds;
- radius/nearby;
- polygon through PostGIS;
- stable sorting and pagination.

### Auth and security

- authentication logic moved to a service;
- Argon2/JWT/refresh rotation retained;
- refresh/logout Origin validation retained;
- production configuration fails fast for unsafe secrets/origins and missing Redis/S3/SMTP requirements;
- distributed Redis rate limiter with per-instance fallback;
- structured request logs, request IDs, Prometheus metrics and optional Sentry;
- readiness covers database, Redis and storage;
- public media keeps exact-address/private-resource rules.

### Media

- real MinIO is part of local Compose;
- S3 path-style adapter and health check;
- public active avatars and published listing images;
- attached media cannot be deleted directly;
- old avatar cleanup;
- failed multi-image synchronization rolls back newly uploaded assets;
- EXIF metadata is removed by server-side re-encoding.

### Mail

- persistent outbox worker;
- `FOR UPDATE SKIP LOCKED` batch delivery;
- retry/failed state;
- local Mailpit SMTP;
- production SMTP fail-fast configuration.

### Frontend state

Messages and reports are no longer persisted as authoritative local browser data outside explicit mock mode. Personal listing comments remain local intentionally because the current UI explicitly promises device-only storage.

No CSS, visual component structure, button design, spacing, typography or approved frontend composition was changed by this audit.

## Tests added

- PostgreSQL/PostGIS integration fixture;
- auth refresh and account deletion;
- listing privacy;
- polygon search;
- room counts including `10+`;
- avatar/media lifecycle;
- messaging and replies;
- MinIO put/read/delete;
- real frontend + FastAPI + PostgreSQL Playwright suite;
- mobile room-filter full-stack scenario.

## Local final audit

Run from a clean checkout:

```bash
bash scripts/final-audit-local.sh
```

The script performs:

- PostGIS/Redis/MinIO/Mailpit startup;
- isolated test database creation;
- Alembic upgrade from an empty database;
- Ruff and Mypy;
- unit and integration pytest suites;
- real MinIO lifecycle test;
- API/readiness/metrics/outbox worker checks;
- frontend lint, typecheck and production build;
- full Playwright regression;
- accessibility;
- visual parity;
- real full-stack Playwright.

## External production items

These cannot be completed or truthfully verified from repository code alone and require the production accounts/environment:

- final API domain and TLS certificate;
- production PostgreSQL/Redis credentials;
- production S3 bucket credentials and lifecycle policy;
- production SMTP credentials and sender-domain verification;
- Google OAuth production client;
- Google Maps key restrictions;
- Sentry DSN or another error-tracking project;
- scheduled encrypted managed-database backups and restoration drill.

Exact production variables and requirements are documented in `deploy/production.env.example`, `docs/production-operations.md` and `README.md`; `backend/.env.example` remains the local-development template. No production secrets are committed.
