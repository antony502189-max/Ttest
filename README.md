# 112233.es

Документы итогового APK-аудита находятся в [`docs/apk-audit`](docs/apk-audit/final-report.md).

[Abrir la versión pública](https://antony502189-max.github.io/Ttest/)

Frontend completo de un marketplace de alquiler de habitaciones en Tenerife. Los anuncios usan datos mock; los mapas se renderizan con Google Maps JavaScript API.

## Desarrollo

```bash
npm install
```

Crea `.env.local` a partir de `.env.example`:

```dotenv
VITE_GOOGLE_MAPS_API_KEY=
VITE_GOOGLE_MAPS_MAP_ID=
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_GOOGLE_CLIENT_ID=
VITE_ENABLE_MOCK_MODE=0
BACKEND_PORT=8000
```

El Map ID es obligatorio en producción para Advanced Markers. El modo local puede usar temporalmente `DEMO_MAP_ID` cuando no se ha configurado uno propio. `.env.local` y el resto de archivos `.env.*` están ignorados por Git.

Para Google sign-in usa el mismo OAuth Web Client ID en `VITE_GOOGLE_CLIENT_ID` y `backend/.env` como `GOOGLE_CLIENT_ID`.
Los datos de catálogo se cargan exclusivamente del backend. El fallback de mock solo se activa de forma explícita con `VITE_ENABLE_MOCK_MODE=1` para desarrollo aislado.

```bash
npm run dev
```

## Backend local

El backend FastAPI usa PostgreSQL + PostGIS. Arranca la base y la API con Docker Compose, aplica las migraciones y abre la documentación en `http://localhost:8000/api/docs`.

```bash
docker compose up -d postgres
docker compose run --rm backend alembic upgrade head
docker compose up -d backend
```

Para crear datos previsibles solo en desarrollo, ejecuta después de las migraciones:

```bash
docker compose run --rm backend python -m app.commands.seed
```

Las solicitudes de recuperación, verificación de e-mail y notificaciones de mensajes se guardan de forma transaccional en `mail_outbox`; el request HTTP no espera a SMTP. En desarrollo la entrega se escribe en el log. En producción configura `SMTP_*` y procesa la cola:

```bash
docker compose run --rm backend python -m app.commands.deliver_outbox
```

Si el puerto 8000 ya está ocupado, ejecuta `BACKEND_PORT=8001 docker compose up -d backend` (en PowerShell: `$env:BACKEND_PORT='8001'`). La API incluye autenticación JWT con refresh cookie, perfiles, anuncios PostGIS, favoritos, ocultos y búsquedas guardadas.

## Verificación

```bash
npm run lint
npm run typecheck
npm run build
cd backend && ruff check app && pytest -q
```

Los scripts reproducibles de QA están en `scripts/`. Los artefactos locales de Playwright se guardan en `output/playwright/` y no se publican en Git.

## Stack

- React 19 + TypeScript
- FastAPI + SQLAlchemy async + Alembic
- PostgreSQL + PostGIS
- Vite 8
- Tailwind CSS 4
- shadcn/ui + Radix UI
- React Router
- Google Maps JavaScript API, Advanced Markers y MarkerClusterer
- Lucide
- Playwright CLI + axe-core para QA
