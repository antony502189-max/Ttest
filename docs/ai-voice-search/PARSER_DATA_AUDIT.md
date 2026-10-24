# Parser and data foundation audit — 2026-10-25

## Scope and evidence

Base: `planning/ai-voice-search-architecture` at `f203807d4507f68b34cd4407e326b3bc671a3552`.
Implementation: `feat/ai-search-parser-audit`. All nine adapters were inspected statically.
The full implementation plan, worker, importer, room models, search filters, migrations,
existing parser/import/dedup tests and the two architecture/import runbooks were reviewed.

**No production dataset or runtime configuration was inspected.** No provider crawl,
production connection, deployment, catalog cleanup, backfill, new provider/region activation,
paid API call or production migration was performed. The included JSON report is generated
from five synthetic source snapshots (four active), not measured production coverage.
Local Docker Desktop's Linux daemon was unavailable (`dockerDesktopLinuxEngine` pipe absent).

## A. Adapter comparison

`G` below means the shared implementation in `external_sources.py`:

- Discovery: provider-host and route allowlists; anchors plus embedded URL values,
  bounded pagination and completeness diagnostics. Anonymous HTTP; existing optional
  Chromium fallback on configured failures. Challenges are not solved.
- Detail: `fetch_listing()` → `request()`; HTTP status/removal/current-detail checks.
  Fotocasa additionally renders an incomplete application shell if enabled.
- Parse: JSON-LD + embedded dictionaries, then listing/meta fallbacks. The generic
  structured object selection is heuristic; not every adapter binds it to the route ID.
  Price/contact/coordinate fallbacks can examine wider document text.
- Normalize: category, rental cadence, EUR price, monthly 1–1000 ceiling, province/country,
  city and coordinate admission; clean description, bounded gallery, optional details.
  A city may be inferred from supported place names in copy; area/address can fall back to city.
- Generic raw: `jsonLd`, `embeddedJson`, first 200,000 HTML characters, `photos_complete`.
  **This is not a complete archived page.** These fields can contain advertiser contacts.

| Adapter | Discovery / detail | Description and available detail | Raw snapshot | Losses, defaults and next evidence task |
|---|---|---|---|---|
| Idealista | G; `/inmueble/<id>` links, room catalogue | G JSON-LD/embedded description → meta; source category added | G | No dedicated full-description DOM parser. Meta may be a summary; source selection can pick an unrelated object. Verify route-bound primary description with anonymized fixtures before changing fallback. |
| Fotocasa | G; `/es/compartir/vivienda/.../<id>/d`; locale-scoped pagination; incomplete-detail rendering flag | Scores embedded candidates; description/detail/body → description DOM → G; heading, price, city, advertiser and dates | G | Scoring is not route-ID proof. DOM regex may stop at a nested closing container. Optional structured policy keys are not mapped. Next: fixtures demonstrating these losses, not a live crawl. |
| Milanuncios | G; four Canary catalogues; bounded five-island eligibility and excluded islands | G; category from URL, municipality fallback from copy | G | No dedicated full-body extraction. Generic page-wide coordinate/price fallback needs source provenance. Municipality inference is not address verification. |
| PisoCompartido | G; `/habitacion/<id>` and provider pagination restrictions | h1 + description/descripcion DOM overrides G; explicit price/date/advertiser; structured gallery preferred | G | Nested DOM truncation possible; fallback image tags can include chrome when no real gallery exists. Tenant policy widgets are not mapped independently. |
| Pisos | G; room/studio/flat/apartment routes; existing holiday route guard | G description; dedicated published gallery, explicit price cadence, provider bedroom metadata, route type and location breadcrumbs | G + cadence/type evidence where available | No dedicated full-description extraction. Existing evidence covers price/type, not pets/children/couples. Gallery completeness prevents replacing a healthy gallery with a partial response. |
| ThinkSpain | G; explicit long/holiday URL families | G description, rental mode from route; municipality from copy | G | No dedicated English policy widget mapping or full-description fallback. Long and holiday admission remain independent. A class existing does not mean it is enabled. |
| AlquilerDocenteCanarias | Public XML sitemap, narrow room/place routes; G detail | h1, description DOM, advertised price/address/city, provider ID, public map attributes | source, external_id, updated_text (+ photos_complete at normalize) | Replaces G raw; original HTML/JSON-LD discarded. Full normalized description survives, but unmapped provider facts cannot be recovered from raw. Contacts intentionally cleared. |
| Flatio | Two bounded offer sitemaps, room/apartment/place routes; G detail | Room/Apartment JSON-LD description; explicit `InStock`, EUR monthly reference unit `MON`, bedrooms, geo, images | source, external_id, availability (+ photos_complete) | Replaces G raw; occupancy/amenity/provider policy keys not mapped. No availability or cadence guessing. Contacts cleared. Preserve a small allowlisted provider-fact set in a later tested adapter change. |
| Habitaclia | Custom public navigation/legacy URLs and room/studio/one-bedroom card classification; bounded pages; existing rendering fallback | DOM plus Next flight public listing state **matched to route ID**; summary.description, property/location/transaction; discovery-image fallback | source, external_id, source_area, public_address, null latitude/longitude (+ photos_complete) | Replaces G raw. Unmapped state facts lost. Coordinates deliberately suppressed because page viewport is not dwelling evidence. Contacts cleared. Do not restore guessed pins. |

Runtime caveat: `configured_sources()` reads `EXTERNAL_IMPORT_SOURCES`; retired-provider
handling is separate. `install_habitaclia_source()` can append Habitaclia when invoked
under production APP_ENV, independently of the normal list. Effective VPS configuration,
reachability, admission rates and source health remain **unverified** here.

## B. What reaches each layer

`NormalizedListing` is shared by all adapters. It retains source identity, title, complete
selected description (no description slicing here), category as room_type/rental_mode,
price/cadence, city/area/public address/province/country, coordinates, photos, contacts,
optional furnishing/bathroom/kitchen/size/capacity/rules, amenities, restrictions, dates and advertiser fields.
Provider-specific keys do not automatically become typed normalized facts.

`normalized_snapshot()` serializes **all dataclass fields**, including `raw_payload`.
Thus `normalized_payload` can itself contain HTML and contacts; it is not a sanitized AI input.
The new audit SQL selects individual JSON fields and never selects either raw object.
The new input builder accepts explicit text/category/fact arguments and rejects arbitrary raw/photo arguments.

Canonical mapping: `upsert()` keeps per-source raw, normalized snapshot and fingerprint.
Only a winning primary snapshot rewrites core Listing fields, contacts, public location,
description/home_description, optional rules and gallery URLs. `room_capacity_v2` is updated
separately in ListingRoomDetails. Promotion restores dates from JSON before applying the same mapping.
Secondary source observations remain in source snapshots; they do not each overwrite the canonical.
Completeness ranking includes description, contacts, location/gallery, **not rule reliability**.
Every successful refresh resets `content_updated_at`, even if fingerprint is unchanged; this
timestamp alone cannot identify a semantic change for future enrichment.

Potential compatibility errors: default booleans interpreted as bans, capacity interpreted
as current household population, `no parejas` treated as one-person capacity, scoped
smoking treated as global permission, pets of one size/species treated as all pets,
substring amenities such as `sin wifi`, title/meta/page-chrome contamination, conflicting
sources resolved merely by completeness. The new bounded policy grammar addresses the
tested simple rule/negation cases; it does not claim to solve all these text problems.

## C. Confirmed bugs and compatibility

### Import fingerprint (fixed)

Original fingerprint omitted pets/children/smoking/capacity/furnishing and other canonical
scalars. Source snapshots were refreshed before the early `unchanged` return, leaving
canonical scalar values stale. Before changing code, the new regression file produced
**19 failures and 1 pass**, including the two extraction defects below.

The existing fingerprint now appends deterministic JSON for previously omitted canonical
scalars, preserving `null` vs `false` vs numbers. Existing text, contact, gallery-order and
partial-gallery components remain. This is a refresh digest, **not the photo-based duplicate
identity algorithm**; source keys, URL identity, advisory locks and dedup thresholds are unchanged.
Existing stored fingerprints will differ once on the next ordinary refresh. That can touch
catalog version and run the existing gallery reconciliation path; no bulk refresh is initiated.
Repeated identical inputs still take the no-op path and do not touch catalog version.

### Unknown/default (measured and constrained; no destructive repair)

Nullable ORM columns still carry defaults: pets/children/smoking/empadronamiento/bills=False,
furnished=True, capacity/size=1, bathroom/kitchen shared, minimum stay/deposit=0.
Migrations 0016/0017/0019 made relevant fields nullable but did not establish provenance.
Owner `ListingWrite` also has defaults; the creation service assigns DTO values, while PATCH
uses `exclude_unset`. A historical stored scalar cannot recover whether a form choice was explicit.

The importer intentionally supplies unknowns and applies the primary snapshot, including None.
The ORM can apply defaults at initial INSERT; the subsequent primary snapshot may then issue
an UPDATE to NULL. In-memory tests verify service assignment; the new PostgreSQL tests reopen
sessions to verify the **persisted** result. Do not infer SQL persistence from mocks alone.
No global ORM defaults, owner DTOs or historical rows are rewritten in this PR.

Compatible provenance proposal (DATA-002/005): future versioned per-source facts with source
record ID, input hash, observation time, evidence source/span or provider field, and separate
explicit/unknown/conditional/conflict status. For owner input preserve explicit field choices
at write time. Existing snapshots can be reconstructed as evidence, labelled as reconstruction,
without pretending a legacy default was an explicit owner/provider statement.

### Capacity (existing preservation verified; fingerprint refresh fixed)

There is no reproduced unconditional “all capacity capped at two” defect in this base.
Migration 0040 preserves rollback-compatible `Listing.room_capacity` capped at 2 and adds
nullable `ListingRoomDetails.room_capacity_v2`. Tests cover 1, 2, 3, 4, 7 and 10 on initial
import, changed-capacity sync, promotion and removal-driven failover. The missing fingerprint
component was the confirmed cause of stale capacity after an optional-only change.

**Remaining bound:** existing importer/owner contract accepts capacity 1–10. A value 11
survives in the source snapshot but does not enter canonical capacity; a test documents this.
The offline evidence packet supports 1–99 for future architecture work. This PR does not widen
the owner API or silently change the existing exact-equality `coalesce(v2, legacy)` filter.
Future AI matching needs a separately approved `confirmed_capacity >= requested_occupants` predicate.

### Source conflicts (reproduced; resolution remains architectural)

Tests cover pets=true / false / unknown across three snapshots, force-primary changes,
capacity changes, source removal, alternative promotion, restoration and canonical identity.
The current canonical follows primary; an unknown primary can clear a previously known value.
Source snapshots keep all observations. The audit reports potentially conflicting active
source records, including bare stored values that may themselves have unknown provenance.
It does not declare them resolved or use inactive records as current votes.

Proposed next resolver (SEARCH-DATA-001, not implemented):

| Active evidence | Proposed result |
|---|---|
| No supported current evidence | unknown |
| One explicit value, others unknown | explicit value, retaining source attribution |
| Several agreeing explicit values | explicit value with all evidence |
| Explicit permit and explicit denial | conflict; no automatic compatibility promise |
| Conditional rule | preserve scope/species/size; do not flatten to unconditional true |
| Closed/retired/removed source | exclude from current votes; retain audit history |
| Owner explicit field vs imported/text result | retain owner provenance; define precedence in ADR |

Freshness thresholds, conditional-vs-denial precedence and promotion ties need an ADR.
No final AI tables, migrations or production resolver were introduced.

## D. Golden extraction

`backend/tests/fixtures/ai_listing_policies.json` contains **26 synthetic annotated cases**.
They include every requested Spanish phrase, conflicts, species/size limits, unknowns,
case/spacing/accent variants, mixed ES/EN, irrelevant marketing/personal statements,
and an intentionally unsupported Russian/complex clause case.
Each annotation states status/value/evidence; omitted information remains unknown.

`listing_evidence.py` recognizes a small set of complete clauses. It retains original
evidence spans and title/description provenance. Global smoking permission stays unknown
for terrace-only permission or an indoor-only prohibition; indoor/outdoor facts remain separate.
Conflicting explicit statements yield conflict. Conditional statements have no unconditional value.
`public_detail_fields()` projects only explicit pets/children/smoking/capacity facts to its
existing nullable fields. Couples/students/scoped evidence is available in the pure evidence
module; no new normalized/DTO fields or room-details coupling were added.

**Precision/recall tradeoff:** compounds not in this bounded grammar can now remain unknown
where the old substring matcher guessed a value. No claim of universal Spanish/English/Russian
understanding is made. The full source description is retained. Other legacy extractors
(amenities, furnishing, bathroom, size, bills) still need evidence-backed hardening; the audit
does not treat their bare values as confirmed provenance.

## E. Read-only audit CLI

Run from `backend` in an environment with the project's dependencies:

```powershell
python -m app.commands.audit_ai_listing_data --input tests/fixtures/ai_listing_audit.json
python -m app.commands.audit_ai_listing_data --input tests/fixtures/ai_listing_audit.json --format markdown --output audit.md
```

For an **authorized test/staging/read-only** PostgreSQL connection, set
`AI_AUDIT_DATABASE_URL` using the environment's secret management, then:

```powershell
python -m app.commands.audit_ai_listing_data --database --output audit.json
```

No DSN CLI argument, normal `DATABASE_URL` fallback, `.env` loading or crawl path exists.
The dedicated connection enables PostgreSQL `default_transaction_read_only=on`, explicitly
sets a READ ONLY repeatable-read transaction, streams selected columns in batches of 500,
then rolls back/disposes. The role should also be read-only. The report writes only an
explicit local output file (or stdout); input-file overwrite is rejected.

Default selection is active source records; `--include-inactive` reports all snapshots,
but cross-source conflicts still use active observations. Report includes per-source n,
distinct canonical counts, title/description presence, min/max/p50/p95 and length histogram,
explicit/conditional/conflict/unknown policy counts for capacity/couples/pets/children/smoking,
amenity presence, public-point presence, conflicts and unknown-provenance counts/share.
Zero denominators yield null / N/A. Quantiles use nearest rank including empty descriptions.

Explicit means evidence reconstructed from stored title/description; it is not a historical
provider-attestation percentage. `unknown_provenance_pct` denominator is nonnull stored fact
values in the documented allowlist; matching bounded text evidence supplies reconstructable
provenance. Unmatched booleans/1/furnishing/amenities are unproven, not automatically confirmed.
`geo_confirmed_pct` is unavailable (null): existing snapshots do not encode verified dwelling
precision. Coordinate presence is reported separately and never relabelled an exact address.

Outputs contain aggregate counts and fixed source labels; no IDs, descriptions, evidence
quotes, advertiser names/contacts or raw HTML. Driver/validation errors are not printed with
payloads or credentials. The tool scans all selected snapshots; its current aggregation keeps
lengths and canonical conflict groups in memory, so measure memory before very large replicas.

[fixture-data-audit.json](fixture-data-audit.json) is the reproducible **synthetic** report:
4 active source records; it is a test of calculations, not a production completeness result.
PARSER-001/002 production coverage and BACKFILL-001 production sizing remain open.

## F. Offline enrichment input

`ai_listing_input.py` provides typed `build_listing_evidence_input()` with no external calls.
It accepts source/record key, canonical UUID, selected title/description, property/rental
categories, optionally known language and explicitly evidenced allowlisted provider facts.
It returns cleaned text, evidence metadata, readiness status and deterministic SHA-256 content hash.

Contacts/URLs/handles/known advertiser name, scripts/styles/navigation/contact blocks and
common token/cookie assignments are removed. Negations, condition phrases and their evidence
remain. Provider facts require a named structured field and strict types/ranges; arbitrary
provider objects cannot be forwarded. Raw payload, coordinates, photos and contact metadata
are outside the function signature. Language stays unknown unless explicitly supplied.
Only-contact/empty text is marked insufficient_source_data; oversize input fails validation
instead of silently truncating a trailing denial.

Hash includes sanitized meaningful text, categories, language, deduplicated/sorted provider
facts and input schema version. Routing IDs, photo/contact changes and observation time are
excluded. The import fingerprint remains independent. A future reconciler should compute
this from the durable source snapshot after import commit; queue identity should include
source record + content hash + extractor/schema version and recheck freshness before accepting a result.

This is an offline prototype, **not a production privacy certification**. Arbitrary names,
obfuscated contacts and unlabelled page chrome in legacy descriptions cannot be guaranteed
removed by a bounded cleaner. Supply the known advertiser name and selected listing text,
review anonymized examples and add an outbound privacy gate before any provider integration.
There is no LLM client, queue, secret, prompt execution or external transmission in this PR.

## G. Verification and changed files

Local environment: isolated Python 3.12.10 venv; project dependencies installed using
`backend/constraints.txt` (no production dependency changes).

- Before fixes: `pytest backend/tests/test_ai_parser_regressions.py -q`: 19 failed, 1 passed.
- Parser/evidence regression run: 225 passed, 1 skipped.
- Final full local non-integration run: **896 passed, 15 skipped**, 4 dependency/deprecation warnings.
- Focused new tests cover CLI calculations/PII/empty samples/repeatability/input immutability,
  read-only SQL transaction order and rollback, types/hash/contact cleaning, full importer
  control flow, optional-only updates, gallery preservation and capacity/promotion.
- Ruff over `backend/app backend/tests`: passed. Mypy over all 117 backend modules: passed.
- New PostgreSQL module: all 8 tests passed as part of the CI integration run below.
  Local execution was unavailable without PostgreSQL/PostGIS; mock results are separate.
- `.github/workflows/ai-parser-foundation.yml` adds planning-PR CI with full unit/lint/type
  checks and importer lifecycle/transaction/removal/Spain/new persistence tests against
  disposable PostgreSQL/PostGIS. Only this CI test database runs the existing migration chain.
- [Successful GitHub run on code revision `6e8500dc`](https://github.com/antony502189-max/Ttest/actions/runs/40136689686):
  **904 passed, 7 skipped** Linux unit tests; **88 passed** PostgreSQL/PostGIS integration tests,
  including all 8 new persistence/audit checks; Ruff and mypy passed. Existing payment backend,
  payment frontend and security static PR checks also passed at that revision. Subsequent
  documentation-only updates record these verified results without changing executable code.

Reproduce the complete local non-integration check from `backend`:

```powershell
python -m pytest tests --ignore=tests/integration -q
python -m ruff check app tests
python -m mypy app
```

For an isolated migrated test database only, with APP_ENV=test and TEST_DATABASE_URL set:

```powershell
python -m pytest tests/integration/test_ai_listing_foundation.py tests/integration/test_external_import_lifecycle.py tests/integration/test_external_import_transaction_boundaries.py tests/integration/test_external_removal.py tests/integration/test_external_spain.py -q
```

Changed files:

- `backend/app/external_sources.py`: fingerprint completeness and conservative policy projection.
- `backend/app/services/listing_evidence.py`: bounded typed policy evidence.
- `backend/app/services/ai_listing_input.py`: offline sanitized typed packet/hash.
- `backend/app/commands/audit_ai_listing_data.py`: read-only stored-data audit.
- `backend/tests/fixtures/ai_listing_policies.json`, `ai_listing_audit.json`: synthetic golden/input fixtures.
- `backend/tests/test_ai_parser_regressions.py`, `test_listing_evidence.py`,
  `test_ai_import_lifecycle.py`, `test_ai_listing_input.py`, `test_audit_ai_listing_data.py`.
- `backend/tests/integration/test_ai_listing_foundation.py`: PostgreSQL persistence/audit checks.
- `.github/workflows/ai-parser-foundation.yml`: isolated planning-PR CI.
- `docs/ai-voice-search/IMPLEMENTATION_PLAN.md`, this report, `fixture-data-audit.json`.

## H. Next three priorities

1. **PARSER-001/002/003, BACKFILL-001:** run this CLI on an authorized replica, review
   anonymized per-source descriptions and explicit provider keys; measure actual gaps and
   memory/runtime before planning backfill cost or targeted detail extraction repairs.
2. **DATA-001/002/004/005/007, SEARCH-DATA-001/002:** approve provenance/freshness/conflict and
   capacity semantics in an ADR, then design expand-only source-facts/search-feature storage.
3. **PARSER-006/007/010, AI-ENRICH-002/004/006:** validate selected provider-fact mappings,
   corpus privacy and input schema; only then add a separately reviewed queue/provider pilot.
   No voice endpoint or paid API integration before the architecture decision.
