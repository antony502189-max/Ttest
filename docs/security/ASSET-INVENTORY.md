# Assets and boundaries

| Asset / component | Exposure and trust | Protection observed / limitation |
|---|---|---|
| React/TypeScript/Vite SPA | Public Nginx through Traefik TLS | In-memory bearer token, HttpOnly refresh cookie, CSP absent |
| FastAPI API | Frontend proxy to private application network | Authentication dependencies, Pydantic schemas, role and owner checks |
| User identity and sessions | PostgreSQL, browser and OAuth | Argon2 passwords; session-bound HS256 access JWT; hashed refresh/reset tokens |
| Listings / photos / videos | User-authored, importer-authored; public only after visibility checks | Ownership and media lifecycle guards; normalized images and video |
| Commercial inventory | Seven advertising slots; homepage hero; TOP intervals | Shared transaction advisory lock, persisted orders, financial review queue |
| Stripe hosted Checkout | Outbound API and inbound signed webhook | Card details stay at Stripe; production keys absent |
| PostgreSQL/PostGIS | Internal data network, persistent volume | Timeouts and transactions; application role is a superuser (SEC-001) |
| Redis | Internal data network | Distributed rate limiting/worker leases; no host-published port |
| MinIO | Internal data network, persistent volume | Bucket has no anonymous policy and no public ACL; application uses separate identity |
| Mail/outbox worker | Data network plus SMTP egress | Durable mail leases, configured STARTTLS; no full SMTP/provider audit |
| External importer / Chromium | Data network plus arbitrary public Internet | URL/DNS/size guards; HTTP connection fix; browser rebinding remains unverified |
| Web push | Fixed browser push provider allowlist | VAPID private key server-only; endpoint and key shape validation |
| Google Maps / Google Identity | Browser SDKs; backend ID-token verifier | Separate OAuth audience config; account-linking authority checks |
| Traefik / Docker host | Public 80/443, privileged Docker API mount | Socket is mounted read-only but still exposes a privileged API to Traefik |
| Release repository / CI | Public GitHub; immutable release directories | SHA/digest pins, schema integrity and backup gates; human review not enforced |
| Encrypted backups and keys | Host-local directory and server-only env file | AES-256-CBC/PBKDF2 plus independent HMAC; off-site recovery unverified |

`API-INVENTORY.md` inventories every declared source HTTP operation, identity
dependency, request/response model and delegates. It also includes hidden
health, metrics and SEO routes. PostgreSQL relations include identity/session,
listing/media, moderation/audit, guest search state, outbox/notifications,
external source/scope/worker state, commercial advertisements/waitlist,
payment orders and a durable financial-event inbox. Retired message models
remain in persistence but no chat HTTP API is exposed.

Rate limits exist at Nginx and Redis-backed middleware. Numeric/list/media
quotas and database statement/lock timeouts are separate controls. They do
not prevent upstream bandwidth saturation or provider-scale DDoS.
