# Deployment

The SPA remains deployable to GitHub Pages with base path `/Ttest/`; retain `VITE_BASE_PATH=/Ttest/` for its build. GitHub Pages hosts only static frontend assets. FastAPI, PostgreSQL/PostGIS, persistent media and SMTP must be deployed separately.

Required production settings:

- `APP_ENV=production`, a strong unique `JWT_SECRET`, and a PostgreSQL/PostGIS `DATABASE_URL`;
- `FRONTEND_ORIGINS=https://antony502189-max.github.io` plus any explicitly authorised frontend origins;
- `FRONTEND_APP_URL=https://antony502189-max.github.io/Ttest` for e-mail links;
- SMTP credentials in `SMTP_*` and a scheduled outbox processor;
- `GOOGLE_CLIENT_ID` only if Google sign-in is used.

Restrict the Google Maps browser key by HTTP referrer, including `https://antony502189-max.github.io/Ttest/*`. Do not place server credentials, database URLs, SMTP passwords or OAuth client secrets in Vite variables or GitHub Pages artifacts.

Run migrations before replacing the API container and configure durable storage for `MEDIA_ROOT` or an equivalent production storage adapter. Health endpoints are `/health/live` and `/health/ready`.
