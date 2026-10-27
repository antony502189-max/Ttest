# Normalized conditions (offline, after #397)

The dialog reads the complete typed intent. Its exhaustive formatter validates
all fifteen criteria and displays hard requirements separately from preferences.
False values, deposit/money/stay units, pet scope and INE/catalog/zone identities
are preserved. An unsupported schema, field or enum produces one fixed notice;
no partial summary or raw JSON is displayed.

Results load the existing owned committed-result endpoint. Ref, hash, session,
version and receipt count must agree before replacing visible results. The latest
editable session has its own summary; failed followups and conflicts cannot
relabel old cards. Paging/map/refresh keep their original result binding.

The user must choose the home mode or no mode constraint for a new conversation.
Only the explicit typed mode may seed session creation; old bodyless creation
remains valid. Subsequent home changes do not mutate an existing conversation.
Choosing a new mode creates a new session; it does not bypass the existing
versioned message/quota operation. Occupants and legacy filters never seed AI.

Local checks: 21 isolated browser contracts (ES/RU/EN, mobile/desktop, ordinary
maps included), 24 disposable PostgreSQL session contracts, 5 HTTP boundary
tests; TypeScript, build, bundle security, i18n, lint and mypy passed. Full unit
regressions and exact-head CI are recorded in the dependent draft PR.

No public runtime, microphone, provider, application database, notification,
deployment or production policy is enabled by this change.
