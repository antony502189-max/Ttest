# Security and privacy: engineering rules

This is a technical implementation guide, not a legal privacy policy. The user-facing legal pages and applicable law must be reviewed separately.

## Trust boundaries

| Data | Storage / access rule |
| --- | --- |
| Access JWT | Memory of authenticated frontend app; send Bearer only to backend |
| Refresh session | Rotated server-side and held in HttpOnly cookie with restrictive scope |
| User profile, owner contact, restrictions, audit | Backend authorization controls access |
| Public listing point | Approximate listing marker permitted by business rules |
| Exact host address/coordinate | Owner/admin-only paths; **must not** leak in public DTOs/markers |
| Media object keys | Private MinIO/S3; controlled upload and read/delete endpoints |
| Browser map visit history | `localStorage` last-point state (180-day validation), never a cross-device account profile |
| Saved searches / favorites / history | Authenticated backend persistence, not equivalent to local map history |
| Commercial campaign payments | Current checkout is a **test** flow; do not describe it as verified real payment integration |

## Validation and abuse prevention

- Backend validates all listing inputs, rental modes, long-term cap (≤1,000 EUR/month), age/status visibility, apartment/room capacity, contact, URLs in listing text, map bounds, polygon vertices, image/video MIME and transformations. Never remove server checks to satisfy a frontend bug.
- CORS uses explicit origins; content and security headers live in `backend/app/main.py` and Nginx. Redis-backed limits protect auth, uploads, reports, publishing and other sensitive operations.
- `/api/v1/admin/*` requires authenticated server-side allowlist/moderation access; a frontend role flag alone is not authorization.
- OAuth settings, refresh cookies, secrets and email verification/reset state require independent rotation/audit. No production token or S3 secret belongs in console logs, screenshots, issue bodies or CI artifacts.
- Region polygons/suggestions are **public reference data**; user/account permissions remain enforced by `visible_query()`. Do not trust a client-supplied `comunidad` label without schema validation.
- Imported sources must respect anonymous-access boundaries, site terms and robots rules. Do not build CAPTCHA bypass, credential harvesting or anti-bot circumvention into the worker.

## Production protections

Production source ships a pinned Compose stack behind Traefik on HTTPS. App services run on private networks; Nginx serves static assets and proxies to FastAPI. PostgreSQL, Redis, MinIO and backend have no host-published service ports. `APP_ENV=production` checks critical env; public OpenAPI/Swagger are off.

- Secret env: `/srv/112233.es/shared/production.env` with mode **600**; never copy to GitHub, chat transcripts or CI.
- PostgreSQL and MinIO backups are encrypted, checksummed and authenticated. Confirm restore drills, not just backup-file existence.
- `deploy-release.sh` serializes operations through `flock`, validates pinned image identities, uses an immutable SHA, and performs public-origin verification before marking success.
- Ordinary release **never** executes broad deduplication, auto-close, gallery repair or physical external-removal maintenance. Production data cleanup needs separate manifest, backup/restore validation and explicit approval.
- Commercial ad upload, fake checkout/approval and publication are separate from genuine payment processing; do not imply a card charge takes place.

## Secure contributions

1. Avoid printing env values, URLs with signed credentials, cookies and authorization headers.
2. Use safe fixture images and synthetic addresses for E2E; do not place actual users or production dumps in tests.
3. New endpoints require Pydantic validation, authorization and rate-limit review; use the `src/api/` transport boundary.
4. Keep user deletion/retention semantics consistent with moderation, media reference counts and transactional outbox.
5. Evaluate location privacy for every new DTO and map marker; city/region labels alone do not confer permission to expose a precise home address.
6. Run `npm run test:security`, `npm run test:bundle-security`, Ruff/Mypy, tests and the production-config check.
7. For incidents, preserve minimal redacted evidence, rotate affected secrets through an approved change, and verify backup/restore capability before data repair.

[Admin moderation](admin-moderation.md) · [Configuration](configuration.md) · [Production operations](production-operations.md) · [API](api.md).
