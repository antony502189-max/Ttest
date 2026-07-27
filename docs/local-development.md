# Local development

Prerequisites: Node 22+, Python 3.13+ and Docker Desktop.

```bash
npm ci
Copy-Item .env.example .env.local
docker compose up -d postgres
docker compose run --rm backend alembic upgrade head
docker compose up -d backend
npm run dev
```

On PowerShell, use `$env:BACKEND_PORT='8001'` before starting Docker if port 8000 is occupied. Set `VITE_API_BASE_URL` to the matching backend URL. `VITE_ENABLE_MOCK_MODE=0` is the default: listings are loaded from FastAPI. Set it to `1` only for isolated frontend development.

Copy `backend/.env.example` to `backend/.env` for non-Docker execution. Configure `GOOGLE_CLIENT_ID` on both backend and frontend only when Google sign-in is enabled. Set `SMTP_*` in production; development delivery writes to logs after running:

```bash
docker compose run --rm backend python -m app.commands.deliver_outbox
```

Media uses `STORAGE_BACKEND=local` and `MEDIA_ROOT=./var/media` by default. To exercise an S3-compatible service set `STORAGE_BACKEND=s3`, `S3_BUCKET`, access credentials and optionally `S3_ENDPOINT_URL`; the same upload URLs work with either backend.
