# Customer video regression audit — 2026-09-09

Observed customer flow:

1. The owner page initially shows existing published listings.
2. The user starts a new publication and enters the location step.
3. Returning to the owner page can transiently render the empty state even though the listings still exist server-side.
4. A fresh publication claims the legacy defaults `Adeje / Armeñime / 38678` before the user has supplied any location.
5. The owner empty-state copy can remain Spanish while the selected UI language is Russian.
6. Administration navigation can pass the first access check and then be treated as denied when a second check fails transiently.

Fix contract:

- `/listings/mine` remains authoritative and its in-flight state must never be represented as an authoritative empty list.
- A same-user server snapshot may bridge a refresh race, but must never leak across account changes.
- Fresh untouched legacy location defaults are converted to an explicit unresolved state; the user must provide an address/postcode or choose a municipality before continuing.
- A non-empty postcode must be exactly five digits.
- Owner-page empty-state copy follows the selected UI language.
- Admin `401/403` remains a real denial. Transient network/5xx failures retry once and then present a recoverable error without logging the user out.

Regression coverage lives in `tests/customer-video-critical-regressions.spec.ts`.
