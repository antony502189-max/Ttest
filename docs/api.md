# HTTP API reference

**Base:** `/api/v1`. Development OpenAPI: `http://localhost:8000/api/docs` (JSON `/api/openapi.json`). **Public production disables these metadata endpoints**; `https://app.112233.es/api/docs` and `/api/openapi.json` must return **404**. Do not publish an unauthenticated Swagger on the VPS.

The browser uses typed functions in `src/api/`. Server request schemas are in `backend/app/schemas/`; routes are in `backend/app/api/v1/`. Contract fields are camelCase for API DTOs even though Python persistence fields are snake_case.

## Major routes

| HTTP | Path suffix | Usage |
| --- | --- | --- |
| POST | `/auth/register`, `/auth/login`, `/auth/google`, `/auth/google/role` | Login/registration and Google role selection |
| GET/POST | `/auth/me`, `/auth/refresh`, `/auth/logout` | Session lifecycle |
| POST | `/auth/forgot-password`, `/auth/reset-password` | Password recovery |
| POST/GET | `/auth/email-verification/request`, `/auth/email-verification/confirm`, `/auth/email-verification/status` | Email verification |
| GET | `/listings/catalog-version`, `/listings/homepage-hero` | Catalog change token, home hero |
| POST | `/listings/search/cards` | Bounded scrolling cards, cursor pagination |
| POST | `/listings/map` | Bounded markers / clusters for a viewport |
| POST | `/listings/regions/counts` | All **17** autonomous-community counts and observed cities under active filters |
| POST | `/listings/search` | Legacy offset-based listing search; keep for compatibility |
| POST | `/listings/cards/resolve` | Resolve up to 100 public listing IDs |
| GET | `/listings/similar/{id}`, `/listings/{id}` | Related cards, listing detail |
| GET/POST/PATCH/DELETE | `/listings/mine`, `/listings`, `/listings/{id}` | Owner listing CRUD; individual methods differ |
| PUT/GET | `/listings/{id}/images` | Gallery associations |
| POST/GET/DELETE | `/uploads`, `/uploads/video`, `/media/{assetId}`, `/uploads/{assetId}` | Private asset lifecycle |
| GET/PUT/DELETE | `/favorites`, `/favorites/{id}` | Personal favorites |
| GET/POST/PATCH/DELETE | `/saved-searches`, `/saved-searches/{id}` | Saved search lifecycle |
| GET/POST/DELETE | `/search-history` | Server-side search terms; distinct from local map history |
| GET/PATCH | `/notifications`, `/notifications/{id}/read` | Notification feed/read state |
| GET/PATCH/DELETE | `/users/me` and related paths | Profile and moderation notices |
| POST | `/reports` | User reports |
| GET/POST | `/advertisements/homepage`, `/advertisements` and related paths | Commercial campaigns |
| GET/POST | `/admin/*` | Protected moderation, ads, importer diagnostics and operations |

See exact method definitions before invoking write endpoints; this table groups routes for orientation, not as a generated OpenAPI replacement.

## Regional search contract

`autonomousCommunity` is an **optional two-character string** `01`–`17` on the `ListingSearchRequest`. A client URL parameter `comunidad=09` is transformed into `autonomousCommunity:"09"` for API requests.

**Get counts for all communities (POST, not GET):**

```bash
curl -fsS http://localhost:8000/api/v1/listings/regions/counts \
  -H 'Content-Type: application/json' \
  -d '{"rentalMode":"long","maxPrice":1000}'
```

Response shape (illustrative counts):

```json
{
  "items": [
    {"id":"01","count":42,"cities":["Sevilla"]},
    {"id":"09","count":73,"cities":["Barcelona"]},
    {"id":"13","count":55,"cities":["Madrid"]}
  ]
}
```

The actual response has **all 17 entries**; zero-count communities are included. The data is read from visible listings in Postgres, **not hard-coded**. `cities` includes distinct city names seen in current matches. The count service removes any incoming region/query term before grouping, while preserving applicable filters such as rental mode and prices. Without a region, search is nationwide; `query:"España"` is treated as a nationwide text term rather than a city-name constraint.

**Search regional cards:**

```bash
curl -fsS http://localhost:8000/api/v1/listings/search/cards \
  -H 'Content-Type: application/json' \
  -d '{"rentalMode":"long","autonomousCommunity":"09","query":"Cataluña","maxPrice":1000,"sort":"newest","limit":20}'
```

This searches published Catalonia listings, including Barcelona, through PostGIS `ST_Intersects` on the listing's public `location` point. It does not require the listing's city/area text to say `Cataluña`. If the region ID is invalid, request validation fails rather than silently searching somewhere else.

Counts and results should be compared using **the same relevant filters**. Do not compare an all-modes count with a long-term-only card query.

## Other search payloads

Search filters include `rentalMode` (`long` | `holiday`), `minPrice`, `maxPrice`, `roomTypes`, `bedroomCounts`, date/stay/capacity/amenities/household flags, and geography:

- Bounding box: all of `minLatitude`, `maxLatitude`, `minLongitude`, `maxLongitude` are required as a unit.
- Radius: `center` + `radiusKm` together; `radiusKm` must be at most **100 km** for this API search predicate. This is **not** the map history's virtual 70 km viewport recall.
- Drawn polygon: `polygon` with at most **100 points**.
- List/card sort: server-approved values such as `newest`, `price_asc`, `price_desc` and favorites-aware sorts.

`POST /listings/search/cards` accepts `limit` 1–50 and an opaque `cursor`. It responds with `items`, exact `total`, `nextCursor` and `previousCursor`. Cursor state is bound to its filters and sort; do not replay after changing query params. Map search uses the same filters plus a viewport and returns up to 300 individual markers at high zoom or bounded grid clusters. `GET /listings/{id}` returns one detail payload, separate from the card projection. For details, see [Spain-scale architecture](spain-scale-architecture.md).

## Auth, errors and privacy

Authenticated routes require `Authorization: Bearer <access-token>`. Access token is short-lived/in memory; refresh token is rotated server-side via an HttpOnly cookie scoped to auth. Backend enforces all admin permissions; client-side hides are never authorization.

Request validation, CORS allowlist, rate limiting (429 + `Retry-After`) and moderation visibility are server responsibilities. Errors use structured JSON with `code`, `message`, and optional `fieldErrors`; exact response status depends on endpoint. Public responses do not expose owner-only address or exact geocoding values. Production does not expose API docs.

**Do not paste production cookies, bearer tokens, credentials or user records into issues or logs.** For release health checks, use the read-only script in [Production operations](production-operations.md).
