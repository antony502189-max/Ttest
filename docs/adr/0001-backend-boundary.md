# ADR 0001: отдельный backend для GitHub Pages frontend

## Контекст

Существующий React/Vite интерфейс публикуется на GitHub Pages по пути `/Ttest/`. GitHub Pages не может исполнять FastAPI, хранить Postgres/PostGIS-данные или выдавать защищённые refresh cookies.

## Решение

- Frontend остаётся статическим приложением с `HashRouter` и `VITE_API_BASE_URL`.
- FastAPI разворачивается отдельно с PostgreSQL/PostGIS и версионированным префиксом `/api/v1`.
- Access JWT живёт только в памяти браузера; refresh token — HttpOnly cookie, ротируемая сервером.
- CORS разрешает только явно перечисленные frontend origins.
- В development media сохраняются в filesystem volume; БД хранит только metadata и opaque storage key.

## Последствия

- GitHub Pages deployment не зависит от Python runtime.
- Для production требуется отдельный API hostname с HTTPS и настройка `VITE_API_BASE_URL`.
- Состояние, требующее синхронизации, переносится за стабильным контрактом `useApp`; purely local comments и временный polygon остаются локальными.
