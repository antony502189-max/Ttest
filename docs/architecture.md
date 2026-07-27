# Architecture

`112233.es` is a React/Vite SPA backed by a modular FastAPI monolith.

```text
React SPA (HashRouter) -> /api/v1 -> FastAPI routers -> SQLAlchemy async -> PostgreSQL + PostGIS
                                      |                 |
                                      |                 +-> Alembic migrations
                                      +-> storage adapter -> local filesystem or S3-compatible object storage
                                      +-> transactional mail_outbox -> delivery command -> dev log or SMTP
```

The frontend uses `src/api/` as its only transport boundary. Access tokens are held in memory; refresh tokens are HttpOnly cookies. Server DTOs use camelCase so that existing TypeScript domain types can be mapped without a UI rewrite.

FastAPI routers cover authentication, users, listings, media, favourites, saved searches, search history, messages, reports and administration. Request IDs and CORS are configured in `backend/app/main.py`. Listings expose only approximate coordinates publicly; exact coordinates and street fields are returned only by owner/admin endpoints.

Email verification and password reset tokens are one-time, hashed records. Creating either token also writes a `mail_outbox` record in the same database transaction. `python -m app.commands.deliver_outbox` delivers pending records without making the HTTP request wait for SMTP.

The frontend design is intentionally not a backend concern: integration changes stay in API/context code and preserve the existing components, routes and Google Maps UI.
