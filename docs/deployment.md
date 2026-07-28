# Deployment

The SPA remains deployable to GitHub Pages with base path `/Ttest/`; retain `VITE_BASE_PATH=/Ttest/` for its build. GitHub Pages hosts only static frontend assets. FastAPI, PostgreSQL/PostGIS, persistent media and SMTP must be deployed separately.

Until a public HTTPS API exists, the Pages workflow deliberately builds with `VITE_ENABLE_MOCK_MODE=1`. It never points a browser at `localhost` and does not pretend a local API is publicly reachable.

## Deploy the backend

Deploy the existing `backend/Dockerfile` as two long-running processes against managed PostgreSQL with PostGIS, Redis, S3-compatible object storage and an SMTP provider:

```bash
# API process
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Separate reliable outbox processor
python -m app.commands.outbox_worker
```

Run `alembic upgrade head` as a release/pre-deploy step before starting a new API revision. Route `/health/live` to a liveness probe and `/health/ready` to the readiness probe. The Docker image already exposes port `8000`; run it behind an HTTPS reverse proxy or the hosting provider's TLS endpoint.

Required production settings:

- `APP_ENV=production`, a strong unique `JWT_SECRET`, and a PostgreSQL/PostGIS `DATABASE_URL`;
- `FRONTEND_ORIGINS=https://antony502189-max.github.io` plus any explicitly authorised frontend origins;
- `FRONTEND_APP_URL=https://antony502189-max.github.io/Ttest` for e-mail links;
- SMTP credentials in `SMTP_*` and a scheduled outbox processor;
- either a durable `MEDIA_ROOT` volume with `STORAGE_BACKEND=local`, or `STORAGE_BACKEND=s3` with `S3_BUCKET`, credentials and, for a compatible provider, `S3_ENDPOINT_URL`.
- `GOOGLE_CLIENT_ID` only if Google sign-in is used.

Restrict the Google Maps browser key by HTTP referrer, including `https://antony502189-max.github.io/Ttest/*`. Do not place server credentials, database URLs, SMTP passwords or OAuth client secrets in Vite variables or GitHub Pages artifacts.

Run migrations before replacing the API container. Health endpoints are `/health/live` and `/health/ready`.

## Switch Pages from demo to the real API

After the backend has a public HTTPS URL, create the GitHub Actions secret `VITE_API_BASE_URL` with its complete versioned value, for example `https://api.example.com/api/v1`, then rerun the Pages deployment. The workflow selects `VITE_ENABLE_MOCK_MODE=0` only when that secret is non-empty; otherwise it remains in autonomous mock mode. Do not use a repository variable for private credentials, do not put `localhost` in Pages, and do not commit the URL if it is not intended to be public.

The backend must allow exactly `https://antony502189-max.github.io` in `FRONTEND_ORIGINS`; cookie and OAuth settings must use the same HTTPS origins. Add the GitHub Pages URL to the Google OAuth authorised JavaScript origins and redirect configuration, and restrict the browser Maps key to `https://antony502189-max.github.io/Ttest/*`.

## Visual baselines

Approved Playwright PNG baselines live only on the `visual-baselines` branch. Normal CI checks that branch out read-only and publishes Playwright report, actual, expected and diff files as artifacts when a comparison fails. It never rewrites a baseline. To replace snapshots, manually inspect the candidate visual result and dispatch **Update Approved Visual Baselines** with its confirmation input set to true; that is the only workflow allowed to push to `visual-baselines`.
