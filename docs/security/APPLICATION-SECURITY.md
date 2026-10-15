# Application review

## Identity and authorization

`core/security.py`, `services/auth.py`, `api/dependencies.py` and auth/user
schemas were reviewed with existing regression suites. Passwords use Argon2;
registration/reset enforce 12–256 characters and preserve password bytes.
Login verifies a dummy hash for unknown accounts, with bounded CPU work.
Forgot-password returns a generic result, locks issuance per account, hashes
single-use expiring tokens and revokes sessions on successful reset. Email
OTP uses an independent HMAC secret in production, expiry/attempt controls
and serialized consumption. Session issuance is bounded and refresh rotation,
reuse-family revocation and access-token session lookup are implemented.

Access JWTs require expiry, subject, type and persisted session ID, and accept
only HS256 with the configured server key. Roles in a JWT are not sufficient
to grant administration; the current account and active AdminAccess allowlist
are checked. Account blocking/deletion and full restrictions are enforced.
Google ID tokens are verified for the configured client and accepted issuer;
non-authoritative third-party email cannot silently take over an existing
local account. Live OAuth provider-console restrictions are unverified.

Remaining identity gaps: admin MFA/step-up is absent; password breach/common
password blocklists are absent; JWT issuer/audience are not explicit. These
need product/adoption decisions and do not establish an observed account
takeover. A controlled password-reset path exists; a distinct authenticated
current-password change flow was not established.

Object boundaries reviewed include listings, uploads/avatar attachments,
favorites/discards, saved searches, history, notifications/moderation notices,
advertisements, paid services and administrative actions. SQL owner predicates
or explicit ownership checks are present in these handlers/delegates, and
cross-user, anonymous, owner and admin cases exist in the integration suite.
`UserUpdateRequest` rejects unknown fields and cannot mass-assign role or email.
Source inventory is complete syntactically; an exhaustive role-by-endpoint
negative matrix is **not** claimed. No production customer identifiers were
enumerated to test authorization.

## API, errors and frontend

Query values use SQLAlchemy expressions/bind parameters; advisory locks use
bound lock keys. Pagination, collection filters, uploads and saved JSON have
bounds. Nginx restricts general JSON bodies to 256 KiB; larger allowances are
scoped to image/video routes. Middleware applies Redis-backed limits with
bounded route buckets and Nginx sanitizes client IP forwarding. Dynamic
payment polling/reconciliation deserves continued abuse-budget review.

Public errors are generic and authenticated API responses default to no-store.
Full exception strings remain in server logging: do not assume that structured
JSON alone redacts SQL parameters or arbitrary exception text. A complete
log/telemetry data-loss-prevention review remains outstanding.

SPA access tokens are held in module memory; the refresh cookie is HttpOnly,
Secure in production and SameSite=Lax, with origin checks for cookie mutation.
Browser storage holds drafts/preferences/session hints, not the production
bearer token. Existing raw innerHTML sites use fixed localization/template
content; SEO HTML uses contextual escaping and script-safe JSON-LD escaping.
Owner-preview media checks trusted API origin; no exploitable token-exfiltration
path was confirmed. External links use noopener/noreferrer. Payment return
paths are server-selected and browser return does not fulfill an order.

Nginx and FastAPI set nosniff, DENY framing, no-referrer and popup-compatible
COOP. Public origin lacks CSP and CSP frame-ancestors (SEC-009); HSTS lacks
includeSubDomains. Do not deploy an untested restrictive CSP: Google Maps,
Identity, existing inline styles and cross-origin media must be validated.
Source maps/mock code are checked by the production bundle policy. No rendering,
layout, theme, map, navigation, language or component source was changed.

## Media and external import

Images: 8 MiB maximum, supported JPEG/PNG/WebP decoded and rewritten, maximum
8,000-pixel dimension and 25-million pixels; derivatives strip original metadata.
Video: 100 MiB input, 60 seconds, 1,920-pixel normalization, 64 MiB output,
bounded concurrency and 480-second transcode deadline. MIME/filename are picker
hints; native decoders inspect content. The new protocol/demuxer allowlists
reject disguised HLS/concat/remote input while preserving MP4/MOV/WebM.
Output is served as data through visibility/owner-aware media endpoints;
original arbitrary filenames are not executable web roots. Quotas, soft
deletion, reference locking and delayed storage-deletion leases are tested.
There is no separate antivirus scan; decoder restrictions are not a malware
scanner or complete native-code sandbox.

HTTP importer requests reject non-public DNS answers, compressed oversized
responses and excessive streamed data. The connection fix closes the gap
between preflight resolution and connect while preserving original Host/TLS
SNI. HTTPX 0.28.1 and HTTPcore 1.0.9 are pinned; private backend integration
must be retested on upgrades. Browser routing blocks private destinations and
WebSockets, but its separate Chromium resolver is not pinned; network-level
browser isolation still needs verification (SEC-013). No external site's
security, CAPTCHA or access controls were tested or bypassed. Approved
source lists, imported data and gallery-preservation policies were unchanged.
