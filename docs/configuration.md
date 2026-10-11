# Configuration and environment variables

**Never commit actual secrets.** There are three different configuration contexts: browser/Vite, development backend/Compose and **VPS-only production**.

## Configuration files

| File | Purpose | May be committed? |
| --- | --- | --- |
| `.env.example` | Browser dev configuration template | Yes; no real credentials |
| `.env.local` | Local Vite configuration | No |
| `backend/.env.example` | Non-Docker FastAPI template | Yes; placeholders only |
| `backend/.env` | Local FastAPI secrets | No |
| `docker-compose.yml` | Local infrastructure and disposable dev credentials | Yes |
| `deploy/production.env.example` | Production key inventory/template | Yes; placeholders only |
| `/srv/112233.es/shared/production.env` | Live VPS secrets, mode **600** | **Never** |
| `docker-compose.production.yml` | Deployment composition and service image pins | Yes |

**Vite `VITE_*` variables are embedded in the frontend bundle and are public**. Never put `JWT_SECRET`, `S3_SECRET_KEY`, `DATABASE_URL`, SMTP credentials or backup encryption keys in a `VITE_*` variable.

## Important browser keys

| Key | Meaning |
| --- | --- |
| `VITE_API_BASE_URL` | Local API, e.g. `http://localhost:8000/api/v1`; production uses its routed same-origin API |
| `VITE_ENABLE_MOCK_MODE` | `0` production/full-stack, `1` isolated fixture UI |
| `VITE_GOOGLE_MAPS_API_KEY` | Referrer-restricted Maps JavaScript browser key (not secret); must have correct API restrictions |
| `VITE_GOOGLE_MAPS_MAP_ID` | Google Maps map-style identifier |
| `VITE_GOOGLE_CLIENT_ID` | Browser OAuth client ID for Google sign-in |
| `VITE_BASE_PATH` | Build/base-path override for particular previews; not proof that GitHub Pages is production |

## Backend / production essentials

| Family | Examples | Notes |
| --- | --- | --- |
| Application | `APP_ENV`, `APP_DOMAIN`, `FRONTEND_APP_URL`, `FRONTEND_ORIGINS` | Production must use correct HTTPS public origin |
| PostgreSQL | `DATABASE_URL`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Never expose ports or connection secrets publicly |
| Signing/session | `JWT_SECRET`, `EMAIL_VERIFICATION_HMAC_SECRET` | Strong, independent secrets; rotate in an approved maintenance window |
| Redis | `REDIS_URL` | Rate limits / worker leases; private Docker network |
| Media | `STORAGE_BACKEND`, `S3_BUCKET`, `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` | Production uses private S3-compatible MinIO |
| Media limits | `MAX_UPLOAD_BYTES`, `MAX_VIDEO_UPLOAD_BYTES`, `MAX_VIDEO_DURATION_SECONDS`, `VIDEO_PROCESSING_CONCURRENCY` | Align UI and backend validation; never disable protections to fix a single upload |
| Email | `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, `SMTP_STARTTLS`, `MAIL_WORKER_*` | Mailpit only in dev; production needs real SMTP |
| Observability | `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE`, `METRICS_ENABLED`, `STRUCTURED_LOGS` | Keep private data out of logs and third-party tracing |
| Backups | `BACKUP_ENCRYPTION_KEY`, `BACKUP_AUTHENTICATION_KEY` | VPS-only; authenticated encrypted backups |
| External imports | `EXTERNAL_IMPORT_ENABLED`, `EXTERNAL_IMPORT_SOURCES`, `EXTERNAL_IMPORT_NATIONWIDE_ENABLED`, `EXTERNAL_IMPORT_PRESERVE_EXISTING_DATA`, `EXTERNAL_REMOVAL_CHECK_ENABLED` | Effective VPS values may differ from committed defaults; confirm before operation |

Use `deploy/production.env.example` to discover the complete set including pool/timeouts, upload quotas, Traefik and source-scope settings. These are **configuration requirements**, not a request to dump production values. For privacy, inspect whether keys are present/valid rather than printing the whole env file into tickets or CI artifacts.

## Production invariants

- Target VPS: `169.58.147.65`; hostname `vmi3640228`; public origin `https://app.112233.es`.
- Compose must use the expected digest-pinned PostgreSQL/Redis/MinIO images; the controlled deploy refuses unintended data-service upgrades.
- `APP_ENV=production` activates strict startup security validation, disables public OpenAPI and expects real dependencies.
- Production `VITE_ENABLE_MOCK_MODE=0`; never deploy seed/demo data or dev SMTP providers.
- Runtime `EXTERNAL_IMPORT_NATIONWIDE_ENABLED` and removal gates are sensitive **state**; do not infer actual values from source defaults. Maintain `EXTERNAL_IMPORT_PRESERVE_EXISTING_DATA=1` and disabled physical-removal behavior absent a separately approved maintenance plan.
- The application distinguishes `long` and `holiday` rental modes; 1,000 EUR monthly cap is long-term only.

## Diagnostics without leaking secrets

```bash
# Read-only current release info (on VPS)
readlink -f /srv/112233.es/current
cat /srv/112233.es/current/build-info.json 2>/dev/null || true
docker ps -a --filter name=ttest-production
```

The public `https://app.112233.es/build-info.json` is suitable for version checks without credentials. Use `deploy/verify-public-origin.sh` / `deploy/smoke-production.sh` for real release acceptance.

[Local development](local-development.md) · [Security](security-and-privacy.md) · [Production operations](production-operations.md).
