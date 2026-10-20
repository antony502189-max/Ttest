# Address predictions and invisible photo identity

## Publication addresses

`src/components/publish-smart-address-autocomplete.tsx` keeps the existing native
input, dropdown, styling, address validation and Spain restriction. It uses Google
Places, not a locally trained model. Predictions start at two characters after a
120 ms debounce. The Places library warms up when the editor binds its address
field (and retries on focus after a load failure).

Modern Places, compatible Places and geocoding remain ordered fallbacks. Each
provider gets 1.8 seconds before the next fallback can start; a slow provider cannot
hold the dropdown indefinitely. This bounds provider waiting, not total response
time. The compatible path resolves only the selected place, instead of geocoding
all five suggestions before displaying them. Selection still validates Spain,
street and the requested building number before changing structured fields.

The editor caches at most 50 successful queries in memory, including language and
location context in the key. Empty/error responses are retried. Escape, outside
clicks, blur, input replacement and edits invalidate pending results; obsolete
requests cannot reopen the dropdown or start additional fallback requests.

Google reference: [Place Autocomplete Data API](https://developers.google.com/maps/documentation/javascript/place-autocomplete-data).

## Hidden photo marks

The existing upload pipeline normalizes images and stores indexed SHA-256
`media_assets.checksum` and 64-bit `media_assets.perceptual_hash`. These are server
metadata linked to a listing or banner through its asset IDs. No visible watermark,
image overlay, new form field or change to layout is involved. No migration or
additional image-processing dependency is needed.

Listing galleries keep their existing conservative comparison, including rental
mode separation and protection for different rooms sharing kitchen/building
photos. Identical content repeated under different uploaded asset IDs counts only
once, so repeating an image cannot dilute a duplicate gallery's overlap score.
Existing create, edit, renewal and moderation checks reuse this comparison.

Commercial banners now check the indexed normalized checksum at both creation and
editing, across accounts and independently of filename, title and destination.
The check runs under the existing advertising capacity transaction lock, so two
concurrent identical submissions cannot both succeed. It excludes the current
campaign while editing. Cancelled and expired campaigns release their identity;
pending payment, review, active and rejected unexpired campaigns retain it.

Conflicts return HTTP 409 with `DUPLICATE_ADVERTISEMENT_IMAGE` and an
`imageAssetId` field error, displayed through existing localized error components.
The 64-bit average hash alone is deliberately not sufficient to reject a
single-image banner: distinct flat-color graphics can share it. Cropped, resized
or recompressed banners that produce different normalized bytes are outside this
exact-content rule. Existing rows already have checksums and need no backfill.

## Verification

- Frontend: typecheck, lint, build, address/autocomplete Playwright regressions.
- Backend: Ruff, duplicate gallery unit regressions and isolated PostGIS
  integration tests for publication and advertising.
- Advertising regressions cover cross-account reuploads, original editing,
  replacement with another creative, cancellation and concurrent submissions.

Local verification on 2026-10-20: 10 address Playwright tests, 33 duplicate/gallery
and advertising unit tests, and 40 PostGIS integration tests passed (publication,
advertising and banner payment lifecycle). TypeScript, Ruff and focused backend
Mypy checks passed; frontend lint passed with existing warnings. Before/after
full-page screenshots of the publication form at 390 px and 1440 px, idle and with
suggestions, were pixel-identical in all four comparisons. The tests use provider
fixtures and do not measure live Google network latency.

Use a disposable database for integration tests: their fixtures truncate public
application tables before each test.
