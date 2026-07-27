# API

Base URL: `/api/v1`. Interactive OpenAPI is available at `/api/docs`; the schema is `/api/openapi.json`.

Authentication endpoints:

- `POST /auth/register`, `/auth/login`, `/auth/google`, `/auth/refresh`, `/auth/logout`
- `GET /auth/me`
- `POST /auth/forgot-password`, `/auth/reset-password`
- `POST /auth/request-email-verification`, `/auth/verify-email`

Domain endpoints are grouped under `/listings`, `/favorites`, `/discarded`, `/saved-searches`, `/search-history`, `/messages`, `/reports`, `/admin`, `/users` and `/uploads`.

`POST /listings/search` accepts rental, price, availability, occupancy, amenities, bounds, radius and polygon filters. Bounds and polygons are evaluated by PostGIS. Public listing responses never include street, postcode or exact coordinates.

Authenticated endpoints require `Authorization: Bearer <access-token>`. The refresh cookie is scoped to `/api/v1/auth`; logout revokes the server-side refresh session. Inputs are validated by Pydantic, CORS uses an allowlist, and login/register attempts are rate limited.

Errors use JSON with `code`, `message` and, where applicable, `fieldErrors`. Do not rely on undocumented local demo data in API consumers.
